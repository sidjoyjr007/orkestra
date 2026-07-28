# Orkestra Framework: Exhaustive Technical Manual

This manual provides a comprehensive, deep-dive explanation of all concepts, sub-concepts, and internal mechanics of the Orkestra framework. For every module, we explain **What it is**, **How it works**, and **When to use it**.

---

## 1. Core Agent Engine (`orkestra.core`)

### 1.1 The `Agent` Class
**What it is:**
The `Agent` is the central processing unit of Orkestra. It represents a single logical persona (e.g., a "Researcher" or "Developer") and manages the interaction between the LLM Provider, Memory, Guardrails, and Tools.

**How it works:**
The engine operates on a stateless-by-design but stateful-by-injection architecture.
- **State Management:** The agent holds a `self.messages` list containing `Message` objects (role, content, tool_calls). 
- **The Execution Loop (`astep`):** 
  When `await agent.astep()` is called, the following strict sequence occurs:

```text
[User] 
  │
  └── (1. Calls astep) ──> [Agent] 
                             │
                             ├── (2. Evaluates User Message) ──> [InputGuardrails]
                             │                                     └──> Returns (Pass / Redact / Block)
                             │
                             ├── (3. Gets Active Plan) ────────> [Planner]
                             │                                     └──> Injects Markdown into System Prompt
                             │
                             ├── (4. Calls agenerate) ─────────> [Provider API]
                             │                                     └──> Returns LLM Response
                             │
                             ├── (5. Evaluates LLM Response) ──> [OutputGuardrails]
                             │                                     └──> Returns (Pass / Feedback / Block)
                             │
  <── (6. Returns Response) ─┘
```

### 1.2 Exception-Driven State Control (`orkestra.core.exceptions`)
**What it is:**
Orkestra completely avoids static `if/else` DAGs (Directed Acyclic Graphs). Instead, it uses custom exceptions to manipulate the control flow of agents globally.

**How it works:**
- `HandoffException`: Raised when an agent voluntarily gives up control to another agent. Caught by the Orchestrator to swap the active agent.
- `WorkflowPausedError`: Raised when the system must immediately halt the current execution thread (used primarily by Background Tools to sleep the agent while an async task runs).
- `ProviderError`: Raised by providers (e.g., rate limits), triggering the `@retry` exponential backoff logic.

### 1.3 Telemetry & Event Bus (`orkestra.events.bus`)
**What it is:**
A publisher/subscriber (Pub/Sub) system that broadcasts real-time telemetry data across the framework.

**How it works:**
- The `EventBus` supports fully asynchronous event firing via `apublish()`.
- Built-in typed events include `AgentStepStarted`, `ToolExecutionStarted`, `TaskCompletedEvent`, and `TokenUsageReported`.
- External systems (like UIs or webhooks) can call `bus.subscribe(EventType, callback)` to listen for state changes without coupling directly to the Agent code.

---

## 2. Comprehensive LLM Provider Support (`orkestra.providers`)

### 2.1 Universal Provider Interface
**What it is:**
A standardized interface (`BaseProvider`) that translates Orkestra's unified data structures into proprietary API schemas.

**How it works:**
Orkestra natively supports a massive array of models:
- **`GeminiProvider`**: Uses the `google-genai` SDK for Gemini 1.5 and 2.5.
- **`AnthropicProvider`**: Connects to Claude 3.5 Sonnet via the `anthropic` SDK.
- **`OpenAIProvider`**: Connects to OpenAI models (GPT-4o) using native tool schema translations via `openai_tools_helper.py`.
- **`vLLMProvider`**: Specifically designed to connect to locally hosted, open-source models (like Llama 3) via a custom `base_url` (e.g., `http://localhost:8000/v1`).
- **`HuggingFaceProvider`**: Connects to HF Inference Endpoints.

### 2.2 API Resilience & Exponential Backoff
**How it works:**
- Provider methods are decorated with `@retry` from the `tenacity` library.
- If the API throws a `ProviderError` (e.g., HTTP 429 Too Many Requests), the wrapper catches it.
- It pauses execution and retries the request using exponential backoff (wait 2 seconds, then 4, then 8) up to 5 times.

---

## 3. Advanced Memory & Compaction (`orkestra.memory`)

### 3.1 Persistent Database Memory (`PostgresMemory`)
**What it is:**
A persistent storage layer that saves agent conversation histories to a PostgreSQL database, partitioned by `session_id`.

**How it works:**
- Uses the `asyncpg` driver for non-blocking database queries.
- **Table Schema:** Stores `id`, `session_id`, `role`, `content`, `tool_calls`, `tool_call_id`, `name`, and `timestamp`.
- **Hydration:** When an agent is initialized, it executes `SELECT * FROM messages WHERE session_id = $1 ORDER BY timestamp ASC` and injects those messages directly into the agent's state.

### 3.2 Context Compaction (`SummarizationStrategy`)
**What it is:**
A mechanism to dynamically compress conversation history to prevent the LLM from exceeding its maximum token context window.

**How it works:**
1. **Trigger Check:** Checks if `len(messages) > max_messages` (e.g., > 50 messages).
2. **Extraction:** Slices the oldest 40 messages from the history array.
3. **Synthesis:** Makes a silent, secondary LLM call with a prompt: *"Summarize the key decisions and facts from this conversation..."*
4. **Replacement:** Deletes the 40 original messages from Postgres, replacing them with a single `Message(role="assistant", content="Summary: ...")`.

---

## 4. Guardrails System (`orkestra.guardrails`)

### 4.1 Evaluation Engines
**What it is:**
A security and formatting enforcement layer that intercepts traffic flowing into (INPUT) and out of (OUTPUT) the LLM.

**How it works:**
Orkestra provides specialized guardrail classes:
- **`RegexGuardrail`**: Evaluates strings instantly against regex patterns. Useful for blocking or redacting PII (like SSNs or emails) natively in memory.
- **`LLMJudgeGuardrail`**: Uses a secondary, cheaper LLM (like Gemini Flash) to act as a judge. It builds a prompt: `"Return EXACTLY 'PASS' if the content passes... or 'FAIL: <reason>'"`. It evaluates the main agent's output for safety, bias, or tone before the user sees it.

### 4.2 Guardrail Actions (BLOCK, REDACT, FEEDBACK)
**How it works:**
1. **BLOCK:** Raises a `SecurityException` and instantly crashes the workflow.
2. **REDACT:** Overwrites sensitive data directly (e.g., masking a credit card number with `***-**-****`) before it is saved to the database.
3. **FEEDBACK (The Steer Mechanic):** Instead of crashing, the framework injects a synthetic system prompt: `SYSTEM WARNING: Your output was invalid JSON. Please fix it.` The agent is prompted to try again on the next turn.

---

## 5. Core Tools Framework (`orkestra.core.tools`)

### 5.1 The `Tool` Class (Sandboxed Execution)
**What it is:**
The base abstraction for actionable functions. By default, Orkestra tools execute in an isolated, dynamically built Docker container.

**How it works:**
- **Automatic Introspection:** The framework parses a Python function's type hints and docstrings into standard JSON Schemas.
- **Sandboxing:** When instantiated, Orkestra creates a `python:3.11-slim` Docker image, pip installs the tool's specific `dependencies`, and executes the LLM's generated Python code inside the container with network isolation (`--network=none`) and strict resource limits (0.5 CPUs, 512MB RAM).

### 5.2 The `HostTool` Override
**What it is:**
A subclass that bypasses the Docker sandbox.

**How it works:**
If a developer explicitly wants a tool to run natively on the host machine (like reading a local file in an IDE), they subclass `HostTool`. It executes the Python function natively inside the main process via standard `asyncio`, retaining full filesystem and network access.

### 5.3 Asynchronous Execution (`BackgroundTool` & `WakeupService`)
**What it is:**
Allows an agent to fire off extremely slow tasks (e.g., training a model, scraping 100 pages) without blocking the thread.

**How it works:**
1. **Launch:** The LLM calls the tool. The tool launches `asyncio.create_task()`.
2. **Sleep:** The tool immediately raises a `WorkflowPausedError`, killing the `AgentRunner` loop so no compute is wasted waiting.
3. **Completion:** When the async task finishes, it fires a `TaskCompletedEvent` onto the `EventBus`.
4. **Wakeup:** The `WakeupService` (in `workflows/background.py`) catches the event, fetches the sleeping agent from the registry, injects the tool result into its memory, and automatically restarts the Orchestrator to resume the agent!

---

## 6. Tool RAG (`orkestra.core.tool_registry`)

### 6.1 Dynamic Tool Injection
**What it is:**
A Retrieval-Augmented Generation system for Tools. Instead of giving an agent 500 tools, it gives the agent 1 tool that searches for other tools.

**How it works:**
1. The agent starts with only an auto-injected `search_tools` tool.
2. The LLM calls `search_tools(query="math calculation")`.
3. Orkestra queries a `chromadb` vector database for tools matching the semantic embedding.
4. The registry returns the JSON schema for `calculator_tool`. Orkestra dynamically appends this schema to `agent.tools`.
5. On the next turn, the LLM calls it natively.

---

## 7. Workspace & Planner (`orkestra.workspace`)

### 7.1 Automatic Truncation & Pagination
**What it is:**
Prevents massive codebase files from crashing the LLM.

**How it works:**
- When reading a file over 100KB, it truncates it and appends `[TRUNCATED]`.
- The engine scans the prompt, detects `[TRUNCATED]`, and dynamically injects a `read_file_chunk` tool.
- The LLM can then natively call `read_file_chunk(start_line=200, end_line=400)` to paginate.

### 7.2 Planner State Injection
**How it works:**
- The agent uses `create_plan` to write a Markdown checklist of sub-tasks. 
- On *every single turn*, the engine fetches the active plan and concatenates it to the very bottom of the agent's `system_prompt`. The LLM constantly sees: `CURRENT PLAN: [x] Read files, [ ] Write code`.

### 7.3 Synergy: Dynamic Planner Injection via Tool RAG
**What it is:**
A hybrid architecture where the Agent is not explicitly given planning tools at startup. Instead, it discovers the ability to plan dynamically via Tool RAG.

**How it works:**
- The agent searches: `search_tools(query="how to break down and track a large project")`.
- The `ToolRegistry` retrieves `create_plan` and `add_task`.
- The LLM dynamically injects these into its own state, creates a plan, and instantly, the Workspace Engine begins injecting the Markdown checklist into the system prompt.

---

## 8. Multi-Agent Orchestration (`orkestra.multi_agent`)

### 8.1 Exception-Based Routing (Handoffs)
**What it is:**
A dynamic routing system avoiding static DAGs.

**How it works:**
- The tool execution physically raises a `HandoffException(target="QA_Agent", context="Please test my code")`.
- The Orchestrator catches this exception, pauses the current agent, loads `"QA_Agent"`, passes the context, and restarts the loop.

### 8.2 Parallel Map-Reduce (`DynamicParallelSubAgentTool`)
**What it is:**
Spawns multiple clones of a Sub-Agent simultaneously.

**How it works:**
- The Manager LLM calls the tool with: `[{"target": "researcher", "task": "Topic A"}, {"target": "researcher", "task": "Topic B"}]`.
- The tool maps over the array, calling `.clone()` to spawn fresh, isolated instances.
- It calls `await asyncio.gather(*tasks)`, executing them in true parallel, concatenates the outputs, and returns it.

### 8.3 Shared Global Scratchpad
**What it is:**
A global key-value store for cross-agent memory.

**How it works:**
- Agents use `read_scratchpad` and `write_scratchpad` tools to pass massive JSON payloads, bypassing standard isolated memory arrays.

### 8.4 State Snapshotting (`AgentStateSerializer` & `SnapshotManager`)
**What it is:**
A persistence layer allowing instant workflow crash recovery.

**How it works:**
- During handoffs, it triggers `SnapshotManager.save_checkpoint()`.
- The `AgentStateSerializer` serializes the agent state, specifically marking which tools are `native` and which are live `mcp` clients.
- If the workflow crashes, `orchestrator.resume("handoff_4")` is called. The Serializer accurately reconstructs the live `httpx.AsyncClient` objects required for MCP tools, rehydrates the memory, and seamlessly restarts the loop.

### 8.5 The Supervisor / Critic Loop (`SupervisedAgent`)
**What it is:**
An invisible proxy wrapper that pits a "Critic" agent against a "Worker" agent.

**How it works:**
- The wrapper secretly passes the Worker's draft response to the Critic.
- If the Critic replies with negative feedback, the proxy injects that feedback directly into the Worker's memory as a system prompt and forces regeneration, looping internally until approved.

---

## 9. Model Context Protocol (MCP) Integration (`orkestra.mcp`)

### 9.1 The `MCPHttpToolkit`
**What it is:**
A native integration to connect Orkestra agents to remote MCP servers over HTTP/SSE.

**How it works:**
- `await toolkit.load_tools()` sends a JSON-RPC 2.0 request (`tools/list`).
- Orkestra dynamically translates the standard MCP `inputSchema` into Orkestra's internal `Tool` schema interface, wrapped in a proxy `MCPTool`.
- `MCPTool.arun()` executes a `tools/call` JSON-RPC POST request, awaits the SSE stream, and returns the result text to the LLM.
