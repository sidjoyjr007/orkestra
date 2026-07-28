import asyncio
import os
from orkestra.providers import GeminiProvider
from orkestra.core.agent import Agent
from orkestra.core.messages import Message
from orkestra.events.bus import EventBus
from orkestra.multi_agent.orchestrator import Orchestrator
from orkestra.multi_agent.registry import AgentRegistry
from orkestra.core.tools import HostTool

# Dummy tool for Tech Support
async def restart_router(**kwargs) -> str:
    return "Router restarted successfully. The internet should be back up!"

tech_tool = HostTool(
    name="restart_router",
    description="Restarts the customer's router remotely.",
    func=restart_router,
    schema={"type": "function", "function": {"name": "restart_router", "description": "Restarts router", "parameters": {"type": "object", "properties": {}}}}
)

# Dummy tool for Billing
async def process_refund(amount: int, **kwargs) -> str:
    return f"Successfully processed a refund for ${amount}."

billing_tool = HostTool(
    name="process_refund",
    description="Processes a refund for a customer.",
    func=process_refund,
    schema={"type": "function", "function": {"name": "process_refund", "description": "Processes refund", "parameters": {"type": "object", "properties": {"amount": {"type": "integer"}}, "required": ["amount"]}}}
)

async def main():
    print("=== Orkestra: 21 Graph Routing & Handoffs ===")
    print("Demonstrating STRICT GRAPH MODE where a Triage agent explicitly hands off to specialized agents.\n")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY environment variable.")
        return
        
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    event_bus = EventBus()
    registry = AgentRegistry()
    
    # 1. Create Agents
    triage_agent = Agent(
        name="Triage",
        description="Greets the user and routes them to the correct department.",
        system_prompt="You are a frontend triage agent. Ask the user what they need. If they need technical help, handoff to TechSupport. If they need a refund or billing help, handoff to Billing.",
        provider=provider,
        id="triage_1"
    )
    
    tech_agent = Agent(
        name="TechSupport",
        description="Helps with technical issues.",
        system_prompt="You are Tech Support. Fix the user's technical issue using your tools.",
        provider=provider,
        tools=[tech_tool],
        id="tech_1"
    )
    
    billing_agent = Agent(
        name="Billing",
        description="Helps with billing issues.",
        system_prompt="You are the Billing department. Process the user's refund using your tools.",
        provider=provider,
        tools=[billing_tool],
        id="billing_1"
    )
    
    # Register them
    registry.register(triage_agent)
    registry.register(tech_agent)
    registry.register(billing_agent)
    
    # 2. Setup the Orchestrator with Strict Graph Topology
    orchestrator = Orchestrator(registry=registry, event_bus=event_bus)
    
    # Define allowed handoff paths (edges)
    orchestrator.add_handoff_edge(source="Triage", target="TechSupport")
    orchestrator.add_handoff_edge(source="Triage", target="Billing")
    # Note: TechSupport and Billing have no outward edges, so they cannot hand off to anyone else!
    
    # 3. Simulate a user hitting the endpoint
    user_prompt = "My internet is completely down. I want a refund of $50!"
    print(f"User: {user_prompt}\n")
    
    # We must seed the message into the starting agent's memory first.
    # Note: Orchestrator clones agents per session, so we should inject the message AFTER the clone, 
    # but for simplicity in scripts, we can inject into the template, or just pass a starting message 
    # to a wrapper function. Here, we'll manually pre-load the template since it's just a demo.
    triage_agent.messages.append(Message(role="user", content=user_prompt))
    
    # Run the orchestrator
    result = await orchestrator.arun(entry_agent_name="Triage", session_id="demo_session_1")
    
    print("\n--- Workflow Complete ---")
    print(f"Final Agent in Control: {result.final_agent_name}")
    print(f"Total Turns: {result.total_turns}")

if __name__ == "__main__":
    asyncio.run(main())
