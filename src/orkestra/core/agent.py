from typing import AsyncIterator, Iterator, List, Optional
import uuid
from orkestra.core.messages import Message, Response, ResponseChunk
from orkestra.providers.base import BaseProvider
from orkestra.memory.base import BaseMemory
from orkestra.events.bus import EventBus
from orkestra.events.base import AgentStepStarted, AgentStepCompleted, TokenUsageReported
from orkestra.core.context import CompactionStrategy, KeepAllStrategy
from orkestra.core.builtin_tools import get_read_file_chunk_tool
from orkestra.core.tools import Tool
from orkestra.workspace.base import BaseWorkspaceStore
from orkestra.workspace.tools import get_planning_tools
from orkestra.guardrails.base import BaseGuardrail, GuardrailStage, GuardrailAction

class Agent:
    """
    Core Agent class representing a logical entity that can process messages
    and generate responses using an underlying LLM provider.
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        system_prompt: str,
        provider: BaseProvider,
        tools: Optional[List[Tool]] = None,
        messages: Optional[List[Message]] = None,
        max_iterations: int = 5,
        memory: Optional[BaseMemory] = None,
        session_id: str = "default-session",
        event_bus: Optional[EventBus] = None,
        compaction: Optional[CompactionStrategy] = None,
        workspace: Optional[BaseWorkspaceStore] = None,
        guardrails: Optional[List[BaseGuardrail]] = None,
        id: Optional[str] = None,
        tool_registry_url: Optional[str] = None,
        artifact_dir: Optional[str] = None
    ):
        """
        Initialize a new Agent.
        
        Args:
            name: The name of the agent (e.g., "ResearcherAgent").
            description: A brief description of what the agent does.
            system_prompt: The core instructions/persona for the agent.
            provider: The LLM provider instance to power this agent.
            tools: Optional list of tools this agent can use.
            messages: Optional initial conversation history.
        """
        self.name = name
        self.description = description
        self.system_prompt = system_prompt
        self.provider = provider
        self.memory = memory
        self.session_id = session_id
        self.tools = tools or []
        self.max_iterations = max_iterations
        self.compaction = compaction
        self.workspace = workspace
        self.guardrails = guardrails or []
        self.event_bus = event_bus or getattr(provider, 'event_bus', None)
        self.id = id or str(uuid.uuid4())
        self.artifact_dir = artifact_dir or f"/tmp/orkestra_artifacts/{self.session_id}"
        
        # Tool RAG initialization
        self.tool_registry_url = tool_registry_url
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0}
        self.tool_registry = None
        if self.tool_registry_url:
            try:
                from orkestra.core.tool_registry import ToolRegistry
                self.tool_registry = ToolRegistry(
                    url=self.tool_registry_url, 
                    agent_id=self.id
                )
            except ImportError:
                pass
            
            # The agent starts with zero tools loaded by default in RAG mode
            self.tools = []
            # Auto-inject the default search_tools capability
            from orkestra.core.builtin_tools import get_search_tools_tool
            self.tools.append(get_search_tools_tool(self))
            
        # Auto-inject planning tools if a workspace is provided
        if self.workspace:
            from orkestra.workspace.tools import get_planning_tools
            planning_tools = get_planning_tools(session_id=self.session_id, workspace=self.workspace)
            # Ensure we don't duplicate tools if the user already passed them
            existing_tool_names = {t.name for t in self.tools}
            for pt in planning_tools:
                if pt.name not in existing_tool_names:
                    self.tools.append(pt)
        
        # Load from memory if available
        if self.memory:
            loaded_msgs = self.memory.get_messages(self.session_id)
            if loaded_msgs:
                self.messages = loaded_msgs
            else:
                self.messages = []
                if messages:
                    for msg in messages:
                        self.add_message(msg)
        else:
            self.messages = messages or []
            
    def clone(self) -> 'Agent':
        """
        Creates a deep-ish clone of the agent for use in sub-sessions or handoffs.
        Ensures that memory (messages) and dynamically injected tools do not leak 
        back into the original template agent.
        """
        import copy
        
        # We want a fresh list, but the tools inside can be shared references
        cloned_tools = list(self.tools) if self.tools else []
        cloned_messages = list(self.messages) if self.messages else []
        cloned_guardrails = list(self.guardrails) if self.guardrails else []
        
        return Agent(
            name=self.name,
            description=self.description,
            system_prompt=self.system_prompt,
            provider=self.provider, # Shared
            tools=cloned_tools,
            messages=cloned_messages,
            max_iterations=self.max_iterations,
            memory=self.memory, # Shared (relies on session_id for isolation)
            session_id=self.session_id,
            event_bus=self.event_bus, # Shared
            compaction=self.compaction,
            workspace=self.workspace, # Shared
            guardrails=cloned_guardrails,
            id=self.id, # Keep same ID to indicate it's the same logical agent profile
            tool_registry_url=self.tool_registry_url,
            artifact_dir=self.artifact_dir
        )

    def add_message(self, message: Message):
        """Add a message to the agent's history and persist to memory if configured."""
        self.messages.append(message)
        if self.memory:
            self.memory.add_message(self.session_id, message)
            
    async def aadd_message(self, message: Message):
        """Add a message asynchronously to history and persist to memory."""
        self.messages.append(message)
        if self.memory:
            if hasattr(self.memory, 'aadd_message'):
                await self.memory.aadd_message(self.session_id, message)
            else:
                self.memory.add_message(self.session_id, message)
                
    async def aapprove_tool(self, tool_call_id: str, tool_name: str, result: str):
        """Used for stateless webhook recovery of HITL tool approvals."""
        await self.aadd_message(Message(role="tool", name=tool_name, content=result, tool_call_id=tool_call_id))


            
    def approve_tool(self, tool_call_id: str, tool_name: str, result: str):
        """Manually approve and inject a tool's result into memory."""
        msg = Message(role="tool", name=tool_name, content=result, tool_call_id=tool_call_id)
        self.add_message(msg)
        
    def reject_tool(self, tool_call_id: str, tool_name: str, reason: str):
        """Manually reject a tool execution."""
        msg = Message(role="tool", name=tool_name, content=f"Execution rejected by human: {reason}", tool_call_id=tool_call_id)
        self.add_message(msg)
        
    async def aapprove_tool(self, tool_call_id: str, tool_name: str, result: str):
        msg = Message(role="tool", name=tool_name, content=result, tool_call_id=tool_call_id)
        await self.aadd_message(msg)
        
    async def areject_tool(self, tool_call_id: str, tool_name: str, reason: str):
        msg = Message(role="tool", name=tool_name, content=f"Execution rejected by human: {reason}", tool_call_id=tool_call_id)
        await self.aadd_message(msg)
        
    async def _aprepare_messages(self, messages: List[Message]) -> List[Message]:
        if self.compaction:
            prepared = await self.compaction.aprocess(messages, self.system_prompt, self.memory, self.session_id)
        else:
            prepared = [Message(role="system", content=self.system_prompt)] + messages
        
        # Dynamically inject active plan if available
        if self.workspace:
            active_plan = await self.workspace.aget_active_plan(self.session_id)
            if active_plan:
                plan_str = f"\n\nCURRENT PLAN:\n{active_plan.to_markdown()}"
                
                # Assume system prompt is at index 0 from compaction
                if prepared and prepared[0].role == "system":
                    prepared[0].content += plan_str
                else:
                    prepared.insert(0, Message(role="system", content=self.system_prompt + plan_str))
                    
        return prepared
        
    def _prepare_messages(self, messages: List[Message]) -> List[Message]:
        import asyncio
        
        if not self.compaction:
            prepared = [Message(role="system", content=self.system_prompt)] + messages
            # Dynamically inject active plan if available
            if self.workspace:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                
                if loop and loop.is_running():
                    import nest_asyncio
                    nest_asyncio.apply()
                
                active_plan = asyncio.run(self.workspace.aget_active_plan(self.session_id))
                if active_plan:
                    plan_str = f"\n\nCURRENT PLAN:\n{active_plan.to_markdown()}"
                    prepared[0].content += plan_str
            return prepared
            
        # Fallback for sync `step`
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
            
        if loop and loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            
        return asyncio.run(self.compaction.aprocess(messages, self.system_prompt, self.memory, self.session_id))

    def step(self, **kwargs) -> Response:
        """
        Execute a single turn of the agent synchronously.
        """
        provider_tools = [tool.schema for tool in self.tools] if self.tools else None
        prepared_messages = self._prepare_messages(self.messages)
        
        if self.event_bus:
            self.event_bus.publish(AgentStepStarted(agent_name=self.name, session_id=self.session_id))
            
        gen_kwargs = kwargs.copy()
        if provider_tools:
            gen_kwargs["tools"] = provider_tools
            
        response = self.provider.generate(messages=prepared_messages, **gen_kwargs)
        self.add_message(response.message)
        
        # Track token usage
        p_tokens = response.usage.get("prompt_tokens", 0)
        c_tokens = response.usage.get("completion_tokens", 0)
        self.usage["prompt_tokens"] += p_tokens
        self.usage["completion_tokens"] += c_tokens
        
        if self.event_bus:
            self.event_bus.publish(TokenUsageReported(
                agent_name=self.name,
                session_id=self.session_id,
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens
            ))
            self.event_bus.publish(AgentStepCompleted(
                agent_name=self.name, 
                session_id=self.session_id,
                response_content=response.message.content,
                tool_calls=len(response.message.tool_calls) if response.message.tool_calls else 0
            ))
            
        return response

    async def astep(self, **kwargs) -> Response:
        """
        Execute a single turn of the agent asynchronously.
        """
        # Run INPUT guardrails on the most recent user message
        if self.messages and self.messages[-1].role == "user" and self.guardrails:
            last_msg = self.messages[-1]
            input_guardrails = [g for g in self.guardrails if g.stage == GuardrailStage.INPUT]
            for g in input_guardrails:
                res = await g.aevaluate(last_msg.content, agent=self)
                if not res.passed:
                    if res.action == GuardrailAction.BLOCK:
                        raise Exception(f"Input blocked by guardrail: {res.message}")
                    elif res.action == GuardrailAction.REDACT:
                        last_msg.content = res.modified_content
                    # FEEDBACK at INPUT stage doesn't make much sense since the user typed it, 
                    # but if specified we can append it as a system message.
                    elif res.action == GuardrailAction.FEEDBACK:
                        await self.aadd_message(Message(role="system", content=f"SYSTEM WARNING (User Input): {res.message}"))
                        
        prepared_messages = await self._aprepare_messages(self.messages)
        
        # Check for TRUNCATED flag to dynamically inject read_file_chunk tool
        needs_read_tool = any("[TRUNCATED]" in (m.content or "") for m in prepared_messages)
        if needs_read_tool:
            has_read_tool = any(t.name == "read_file_chunk" for t in self.tools)
            if not has_read_tool:
                self.tools.append(get_read_file_chunk_tool(self.artifact_dir))
                
        # Dynamically inject planning tools based on workspace state
        if self.workspace:
            planning_tools = get_planning_tools(self.session_id, self.workspace)
            active_plan = await self.workspace.aget_active_plan(self.session_id)
            
            # We want to keep tools clean, so let's filter out old planning tools first
            self.tools = [t for t in self.tools if t.name not in ["create_plan", "update_task", "add_task"]]
            
            # Inject only what's needed
            for pt in planning_tools:
                if active_plan:
                    # If there IS an active plan, we need all tools (create_plan to override, update/add to manage)
                    self.tools.append(pt)
                else:
                    # If NO active plan, we only need create_plan
                    if pt.name == "create_plan":
                        self.tools.append(pt)
            
        provider_tools = [tool.schema for tool in self.tools] if self.tools else None
        
        if self.event_bus:
            await self.event_bus.apublish(AgentStepStarted(agent_name=self.name, session_id=self.session_id))
            
        gen_kwargs = kwargs.copy()
        if provider_tools:
            gen_kwargs["tools"] = provider_tools
            
        response = await self.provider.agenerate(messages=prepared_messages, **gen_kwargs)
        
        # Run OUTPUT guardrails on the LLM's response
        if self.guardrails and response.message.content:
            output_guardrails = [g for g in self.guardrails if g.stage == GuardrailStage.OUTPUT]
            for g in output_guardrails:
                res = await g.aevaluate(response.message.content, agent=self)
                if not res.passed:
                    if res.action == GuardrailAction.BLOCK:
                        # Clear the message so it doesn't get saved to memory
                        response.message.content = ""
                        response.message.tool_calls = []
                        raise Exception(f"Output blocked by guardrail: {res.message}")
                    elif res.action == GuardrailAction.REDACT:
                        response.message.content = res.modified_content
                    elif res.action == GuardrailAction.FEEDBACK:
                        # Inject feedback warning so the LLM sees it on the next turn
                        await self.aadd_message(Message(role="system", content=f"SYSTEM WARNING (Your Output): {res.message}"))
                        
        await self.aadd_message(response.message)
        
        # Track token usage
        p_tokens = response.usage.get("prompt_tokens", 0)
        c_tokens = response.usage.get("completion_tokens", 0)
        self.usage["prompt_tokens"] += p_tokens
        self.usage["completion_tokens"] += c_tokens
        
        if self.event_bus:
            await self.event_bus.apublish(TokenUsageReported(
                agent_name=self.name,
                session_id=self.session_id,
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens
            ))
            await self.event_bus.apublish(AgentStepCompleted(
                agent_name=self.name, 
                session_id=self.session_id,
                response_content=response.message.content,
                tool_calls=len(response.message.tool_calls) if response.message.tool_calls else 0
            ))
            
        # Run OUTPUT guardrails on the generated response
        if response.message.content and self.guardrails:
            output_guardrails = [g for g in self.guardrails if g.stage == GuardrailStage.OUTPUT]
            for g in output_guardrails:
                res = await g.aevaluate(response.message.content, agent=self)
                if not res.passed:
                    if res.action == GuardrailAction.BLOCK:
                        raise Exception(f"Output blocked by guardrail: {res.message}")
                    elif res.action == GuardrailAction.REDACT:
                        response.message.content = res.modified_content
                        # Need to update the stored message as well
                        self.messages[-1].content = res.modified_content
                    elif res.action == GuardrailAction.FEEDBACK:
                        # Agent generated bad output, steer it
                        warning = f"SYSTEM WARNING (Output Feedback): {res.message}"
                        await self.aadd_message(Message(role="system", content=warning))
                        # We return the response anyway, but next turn it will see the warning
                        
        return response

    def stream(self, **kwargs) -> Iterator[ResponseChunk]:
        # Stream the agents response synchronously. Note: Tool execution is not natively looped in streaming.
        prepared_messages = self._prepare_messages(self.messages)
        if self.tools:
            kwargs["tools"] = [tool.schema for tool in self.tools]
        return self.provider.generate_stream(messages=prepared_messages, **kwargs)

    def astream(self, **kwargs) -> AsyncIterator[ResponseChunk]:
        # Stream the agents response asynchronously.
        prepared_messages = self._prepare_messages(self.messages)
        if self.tools:
            kwargs["tools"] = [tool.schema for tool in self.tools]
        return self.provider.agenerate_stream(messages=prepared_messages, **kwargs)
