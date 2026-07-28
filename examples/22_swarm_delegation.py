import asyncio
import os
from orkestra.providers import GeminiProvider
from orkestra.core.agent import Agent
from orkestra.core.messages import Message
from orkestra.events.bus import EventBus
from orkestra.multi_agent.orchestrator import Orchestrator
from orkestra.multi_agent.registry import AgentRegistry
from orkestra.core.tools import HostTool

# Dummy tool for Researcher
async def search_database(query: str, **kwargs) -> str:
    if "market" in query.lower():
        return "Market Data: Sales are up 20% this quarter in the EU region."
    return "No data found."

search_tool = HostTool(
    name="search_database",
    description="Searches the internal corporate database.",
    func=search_database,
    schema={"type": "function", "function": {"name": "search_database", "description": "Search DB", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}}
)

async def main():
    print("=== Orkestra: 22 Swarm Delegation (Sub-Agents) ===")
    print("Demonstrating SWARM MODE where a Manager agent dynamically spawns worker sub-agents.\n")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY environment variable.")
        return
        
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    event_bus = EventBus()
    registry = AgentRegistry()
    
    # 1. Create Agents
    ceo_agent = Agent(
        name="CEO",
        description="The big boss who delegates tasks.",
        system_prompt="You are the CEO. The user will ask for a report. You should delegate the data gathering to the Researcher, and then delegate the report writing to the Writer. Synthesize their results.",
        provider=provider,
        id="ceo_1"
    )
    
    researcher_agent = Agent(
        name="Researcher",
        description="Gathers data from internal databases.",
        system_prompt="You are a data researcher. Use your tool to answer the manager's query.",
        provider=provider,
        tools=[search_tool],
        id="researcher_1"
    )
    
    writer_agent = Agent(
        name="Writer",
        description="Writes professional corporate reports.",
        system_prompt="You are a corporate copywriter. Write a short, professional 2-sentence summary based on the data provided.",
        provider=provider,
        id="writer_1"
    )
    
    # Register them
    registry.register(ceo_agent)
    registry.register(researcher_agent)
    registry.register(writer_agent)
    
    # 2. Setup the Orchestrator (No graph edges means SWARM MODE is active)
    orchestrator = Orchestrator(registry=registry, event_bus=event_bus)
    
    # 3. Simulate a user request
    user_prompt = "I need a quick market report."
    print(f"User: {user_prompt}\n")
    
    # Preload user message into template for demo purposes
    ceo_agent.messages.append(Message(role="user", content=user_prompt))
    
    # Run the orchestrator
    result = await orchestrator.arun(entry_agent_name="CEO", session_id="swarm_session_1", max_turns=5)
    
    print("\n--- Workflow Complete ---")
    print(f"Final Agent in Control: {result.final_agent_name}")
    print(f"Total Turns: {result.total_turns}")
    
    # Print CEO final output
    ceo = registry.get_agent("CEO")
    if ceo:
        # Since orchestrator cloned CEO, we can't easily get the live instance's memory from the local var.
        # But wait, in memory-backed mode it would save it. Since we are using in-memory default, 
        # the final result was printed to standard out by the agents, so that's sufficient for this demo.
        pass

if __name__ == "__main__":
    asyncio.run(main())
