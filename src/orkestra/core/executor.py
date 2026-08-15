import json
import asyncio
import os
from typing import List, Dict, Optional, Any
from orkestra.core.messages import Message, ToolCall
from orkestra.core.exceptions import WorkflowPausedError
from orkestra.events.bus import EventBus
from orkestra.events.base import ToolExecutionStarted, ToolExecutionCompleted, HumanApprovalRequested, HumanApprovalProvided, WorkflowPaused, GuardrailTriggered
from orkestra.guardrails.base import GuardrailStage, GuardrailAction
from orkestra.core.prompts import TOOL_LOOP_WARNING
from orkestra.core.swarm import HandoffException
from orkestra.core.telemetry import get_logger

logger = get_logger("orkestra.core.executor")

class ToolExecutor:
    """
    Handles the execution of tools on behalf of an Agent.
    Responsible for Guardrails, HITL (Human-in-the-loop) approvals, truncation, and event emission.
    """
    def __init__(self, agent, event_bus: Optional[EventBus] = None):
        self.agent = agent
        self.event_bus = event_bus
        self._pending_approvals: Dict[str, asyncio.Future] = {}
        
        if self.event_bus:
            self.event_bus.subscribe(HumanApprovalProvided, self._on_approval_provided)
            
    def _on_approval_provided(self, event: HumanApprovalProvided):
        if event.tool_call_id in self._pending_approvals:
            if not self._pending_approvals[event.tool_call_id].done():
                self._pending_approvals[event.tool_call_id].set_result(event.result)
                
    def _count_historical_tool_calls(self, tool_call: ToolCall) -> int:
        count = 0
        for msg in reversed(self.agent.messages):
            if msg.role == "assistant" and msg.tool_calls:
                for tc in msg.tool_calls:
                    if tc.function_name == tool_call.function_name and tc.function_arguments == tool_call.function_arguments:
                        count += 1
        return count

    def execute(self, tool_calls: List[ToolCall]):
        tool_map = {tool.name: tool for tool in self.agent.tools}
        
        for tool_call in tool_calls:
            tool_name = tool_call.function_name
            tool_args_str = tool_call.function_arguments
            kwargs_args = json.loads(tool_args_str) if tool_args_str else {}
            
            # Anti-Loop Steering Mechanism
            historical_count = self._count_historical_tool_calls(tool_call)
            if historical_count >= 3:
                result = TOOL_LOOP_WARNING.format(tool_name=tool_name, historical_count=historical_count)
                if self.event_bus:
                    self.event_bus.publish(ToolExecutionCompleted(agent_name=self.agent.name, session_id=self.agent.session_id, tool_name=tool_name, tool_call_id=tool_call.id, result=result, error=result))
                self.agent.add_message(Message(role="tool", name=tool_name, content=result, tool_call_id=tool_call.id))
                continue
            
            tool = tool_map.get(tool_name)
            if not tool:
                result = f"Error: Tool '{tool_name}' not found."
                error = result
                
            # Action Guardrails (Sync wrapper over async evaluate)
            action_guardrails = [g for g in self.agent.guardrails if g.stage == GuardrailStage.ACTION] if hasattr(self.agent, 'guardrails') else []
            blocked_by_guardrail = False
            for g in action_guardrails:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                    
                if loop and loop.is_running():
                    import nest_asyncio
                    nest_asyncio.apply()
                    
                res = asyncio.run(g.aevaluate(tool_args_str, context={"tool_name": tool_name, "tool_args": kwargs_args}, agent=self.agent))
                if not res.passed:
                    if res.action == GuardrailAction.BLOCK:
                        result = f"Error: Tool execution blocked by guardrail: {res.message}"
                        if self.event_bus:
                            self.event_bus.publish(GuardrailTriggered(
                                agent_name=self.agent.name,
                                session_id=self.agent.session_id,
                                stage=GuardrailStage.ACTION.value,
                                action_taken=GuardrailAction.BLOCK.value,
                                message=res.message,
                                modified_content=res.modified_content
                            ))
                            self.event_bus.publish(ToolExecutionCompleted(agent_name=self.agent.name, session_id=self.agent.session_id, tool_name=tool_name, tool_call_id=tool_call.id, result=result, error=result))
                        self.agent.add_message(Message(role="tool", name=tool_name, content=result, tool_call_id=tool_call.id))
                        blocked_by_guardrail = True
                        break
                    elif res.action == GuardrailAction.FEEDBACK:
                        result = f"SYSTEM WARNING: Guardrail failed for tool '{tool_name}': {res.message}. Please reconsider your action."
                        if self.event_bus:
                            self.event_bus.publish(GuardrailTriggered(
                                agent_name=self.agent.name,
                                session_id=self.agent.session_id,
                                stage=GuardrailStage.ACTION.value,
                                action_taken=GuardrailAction.FEEDBACK.value,
                                message=res.message,
                                modified_content=res.modified_content
                            ))
                            self.event_bus.publish(ToolExecutionCompleted(agent_name=self.agent.name, session_id=self.agent.session_id, tool_name=tool_name, tool_call_id=tool_call.id, result=result, error=result))
                        self.agent.add_message(Message(role="tool", name=tool_name, content=result, tool_call_id=tool_call.id))
                        blocked_by_guardrail = True
                        break
                    elif res.action == GuardrailAction.REDACT:
                        if self.event_bus:
                            self.event_bus.publish(GuardrailTriggered(
                                agent_name=self.agent.name,
                                session_id=self.agent.session_id,
                                stage=GuardrailStage.ACTION.value,
                                action_taken=GuardrailAction.REDACT.value,
                                message=res.message,
                                modified_content=res.modified_content
                            ))
                        tool_args_str = res.modified_content
                        kwargs_args = json.loads(tool_args_str) if tool_args_str else {}
                        
            if blocked_by_guardrail:
                continue
                
            if tool:
                if getattr(tool, 'requires_approval', False):
                    # Check if already approved via HITL injection (must come after the requesting assistant message)
                    last_assistant_idx = None
                    for idx, msg in enumerate(reversed(self.agent.messages)):
                        if msg.role == "assistant":
                            last_assistant_idx = len(self.agent.messages) - 1 - idx
                            break
                            
                    is_approved = False
                    if last_assistant_idx is not None:
                        is_approved = any(
                            msg.role == "system" and msg.content and f"[HITL_APPROVED] {tool_call.id}" in msg.content
                            for msg in self.agent.messages[last_assistant_idx + 1:]
                        )
                    
                    if not is_approved:
                        if self.event_bus:
                            self.event_bus.publish(HumanApprovalRequested(agent_name=self.agent.name, tool_name=tool_name, tool_call_id=tool_call.id, tool_args=kwargs_args))
                            self.event_bus.publish(WorkflowPaused(agent_name=self.agent.name))
                        logger.info(f"Execution paused. Tool '{tool_name}' requires human approval.", extra={"extra_data": {"agent_id": self.agent.id, "tool_name": tool_name}})
                        raise WorkflowPausedError(f"Workflow paused: Tool '{tool_name}' requires human approval.", tool_name=tool_name, tool_call_id=tool_call.id, tool_args=kwargs_args)
                    
                try:
                    logger.info(f"Executing tool '{tool_name}'", extra={"extra_data": {"agent_id": self.agent.id, "tool_name": tool_name}})
                    
                    # Inject hidden context parameters for advanced tools (like BackgroundTool)
                    kwargs_args["_session_id"] = self.agent.session_id
                    kwargs_args["_tool_call_id"] = tool_call.id
                    kwargs_args["_agent_name"] = self.agent.name
                    
                    if self.event_bus:
                        self.event_bus.publish(ToolExecutionStarted(agent_name=self.agent.name, session_id=self.agent.session_id, tool_name=tool_name, tool_call_id=tool_call.id, tool_args=kwargs_args))
                    result = tool.run(**kwargs_args)
                    error = None
                except WorkflowPausedError as e:
                    raise e
                except HandoffException as e:
                    raise e
                except Exception as e:
                    logger.error(f"Error executing tool '{tool_name}'", exc_info=True, extra={"extra_data": {"agent_id": self.agent.id, "tool_name": tool_name}})
                    result = f"Error executing '{tool_name}': {str(e)}"
                    error = result
                    
            if not isinstance(result, str):
                try:
                    result = json.dumps(result)
                except Exception:
                    result = str(result)
                    
            if tool and getattr(tool, 'max_result_length', None) is not None and len(result) > tool.max_result_length:
                artifact_dir = f"/tmp/orkestra_artifacts/{self.agent.session_id}"
                os.makedirs(artifact_dir, exist_ok=True)
                artifact_path = os.path.join(artifact_dir, f"{tool_call.id}.txt")
                with open(artifact_path, "w") as f:
                    f.write(result)
                result = result[:tool.max_result_length] + f"\n... [TRUNCATED] The output exceeded the maximum length. The full raw output was automatically saved to: {artifact_path}."
                    
            if self.event_bus:
                self.event_bus.publish(ToolExecutionCompleted(agent_name=self.agent.name, session_id=self.agent.session_id, tool_name=tool_name, tool_call_id=tool_call.id, result=result, error=error))
            
            self.agent.add_message(Message(role="tool", name=tool_name, content=result, tool_call_id=tool_call.id))

    async def _aexecute_single_tool(self, tool_call: ToolCall, tool_map: Dict[str, Any]):
        tool_name = tool_call.function_name
        tool_args_str = tool_call.function_arguments
        kwargs_args = json.loads(tool_args_str) if tool_args_str else {}
        
        # Action Guardrails
        action_guardrails = [g for g in self.agent.guardrails if g.stage == GuardrailStage.ACTION] if hasattr(self.agent, 'guardrails') else []
        blocked_by_guardrail = False
        for g in action_guardrails:
            res = await g.aevaluate(tool_args_str, context={"tool_name": tool_name, "tool_args": kwargs_args}, agent=self.agent)
            if not res.passed:
                if res.action == GuardrailAction.BLOCK:
                    result = f"Error: Tool execution blocked by guardrail: {res.message}"
                    if self.event_bus:
                        await self.event_bus.apublish(ToolExecutionCompleted(agent_name=self.agent.name, session_id=self.agent.session_id, tool_name=tool_name, tool_call_id=tool_call.id, result=result, error=result))
                    await self.agent.aadd_message(Message(role="tool", name=tool_name, content=result, tool_call_id=tool_call.id))
                    blocked_by_guardrail = True
                    break
                elif res.action == GuardrailAction.FEEDBACK:
                    result = f"SYSTEM WARNING: Guardrail failed for tool '{tool_name}': {res.message}. Please reconsider your action."
                    if self.event_bus:
                        await self.event_bus.apublish(ToolExecutionCompleted(agent_name=self.agent.name, session_id=self.agent.session_id, tool_name=tool_name, tool_call_id=tool_call.id, result=result, error=result))
                    await self.agent.aadd_message(Message(role="tool", name=tool_name, content=result, tool_call_id=tool_call.id))
                    blocked_by_guardrail = True
                    break
                elif res.action == GuardrailAction.REDACT:
                    tool_args_str = res.modified_content
                    kwargs_args = json.loads(tool_args_str) if tool_args_str else {}
                    
        if blocked_by_guardrail:
            return
        
        # Anti-Loop Steering Mechanism
        historical_count = self._count_historical_tool_calls(tool_call)
        if historical_count >= 3:
            result = TOOL_LOOP_WARNING.format(tool_name=tool_name, historical_count=historical_count)
            if self.event_bus:
                await self.event_bus.apublish(ToolExecutionCompleted(agent_name=self.agent.name, session_id=self.agent.session_id, tool_name=tool_name, tool_call_id=tool_call.id, result=result, error=result))
            await self.agent.aadd_message(Message(role="tool", name=tool_name, content=result, tool_call_id=tool_call.id))
            return
        
        tool = tool_map.get(tool_name)
        if not tool:
            result = f"Error: Tool '{tool_name}' not found."
            error = result
        else:
            if getattr(tool, 'requires_approval', False):
                last_assistant_idx = None
                for idx, msg in enumerate(reversed(self.agent.messages)):
                    if msg.role == "assistant":
                        last_assistant_idx = len(self.agent.messages) - 1 - idx
                        break
                        
                is_approved = False
                if last_assistant_idx is not None:
                    is_approved = any(
                        msg.role == "system" and msg.content and f"[HITL_APPROVED] {tool_call.id}" in msg.content
                        for msg in self.agent.messages[last_assistant_idx + 1:]
                    )
                
                if not is_approved:
                    if self.event_bus:
                        await self.event_bus.apublish(HumanApprovalRequested(agent_name=self.agent.name, tool_name=tool_name, tool_call_id=tool_call.id, tool_args=kwargs_args))
                        await self.event_bus.apublish(WorkflowPaused(agent_name=self.agent.name))
                    raise WorkflowPausedError(f"Workflow paused: Tool '{tool_name}' requires human approval.", tool_name=tool_name, tool_call_id=tool_call.id, tool_args=kwargs_args)
                
            try:
                logger.info(f"Executing tool '{tool_name}'", extra={"extra_data": {"agent_id": self.agent.id, "tool_name": tool_name}})
                
                kwargs_args["_session_id"] = self.agent.session_id
                kwargs_args["_tool_call_id"] = tool_call.id
                kwargs_args["_agent_name"] = self.agent.name
                
                if self.event_bus:
                    await self.event_bus.apublish(ToolExecutionStarted(agent_name=self.agent.name, session_id=self.agent.session_id, tool_name=tool_name, tool_call_id=tool_call.id, tool_args=kwargs_args))
                result = await tool.arun(**kwargs_args)
                error = None
            except WorkflowPausedError as e:
                raise e
            except HandoffException as e:
                raise e
            except Exception as e:
                logger.error(f"Error executing tool '{tool_name}'", exc_info=True, extra={"extra_data": {"agent_id": self.agent.id, "tool_name": tool_name}})
                result = f"Error executing '{tool_name}': {str(e)}"
                error = result
                
        if tool and getattr(tool, 'max_result_length', None) is not None and len(result) > tool.max_result_length:
            artifact_dir = f"/tmp/orkestra_artifacts/{self.agent.session_id}"
            os.makedirs(artifact_dir, exist_ok=True)
            artifact_path = os.path.join(artifact_dir, f"{tool_call.id}.txt")
            
            def write_artifact():
                with open(artifact_path, "w") as f:
                    f.write(result)
            await asyncio.to_thread(write_artifact)
            
            result = result[:tool.max_result_length] + f"\n... [TRUNCATED] The output exceeded the maximum length. The full raw output was automatically saved to: {artifact_path}."
                
        if self.event_bus:
            await self.event_bus.apublish(ToolExecutionCompleted(agent_name=self.agent.name, session_id=self.agent.session_id, tool_name=tool_name, tool_call_id=tool_call.id, result=result, error=error))
        
        await self.agent.aadd_message(Message(role="tool", name=tool_name, content=result, tool_call_id=tool_call.id))

    async def aexecute(self, tool_calls: List[ToolCall]):
        tool_map = {tool.name: tool for tool in self.agent.tools}
        tasks = [self._aexecute_single_tool(tc, tool_map) for tc in tool_calls]
        await asyncio.gather(*tasks, return_exceptions=False)
