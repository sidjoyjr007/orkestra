import React, { useState } from "react"
import { 
  Info, Wrench, CheckCircle2, AlertTriangle, PlayCircle, StopCircle, Zap,
  Activity, ArrowRightLeft, Network, ShieldCheck, ShieldAlert,
  Database, Save, Search, FileText, Clock3, ChevronUp, ChevronDown
} from "lucide-react"

export function EventLogItem({ event }) {
  const [expanded, setExpanded] = useState(false)
  
  const { event_type, details, timestamp } = event
  const timeStr = new Date(timestamp).toLocaleTimeString()
  
  let icon = <Info className="h-3.5 w-3.5 text-blue-500" />
  let borderColor = "border-blue-500/30"
  let bgClass = ""
  let content = null
  let title = event_type
  let isError = false
  
  const safeStringify = (val, isExpanded) => {
    if (val === null || val === undefined) return ""
    const str = typeof val === 'object' ? JSON.stringify(val, null, 2) : String(val)
    if (str.length > 200 && !isExpanded) {
      return str.substring(0, 200) + "..."
    }
    return str
  }

  const isLongStr = (val) => {
    if (val === null || val === undefined) return false
    const str = typeof val === 'object' ? JSON.stringify(val, null, 2) : String(val)
    return str.length > 200
  }

  switch (event_type) {
    case "ToolExecutionStarted":
      icon = <Wrench className="h-3.5 w-3.5 text-purple-500" />
      borderColor = "border-purple-500/40"
      bgClass = "bg-purple-500/5"
      title = `Tool Started: ${details.tool_name}`
      content = (
        <div className="space-y-1 mt-1.5">
          <div className="text-[10px] uppercase text-muted-foreground font-semibold">Arguments:</div>
          <pre className="bg-background border rounded-md p-2 text-[10px] overflow-x-auto text-muted-foreground">
            {JSON.stringify(details.tool_args, null, 2)}
          </pre>
        </div>
      )
      break
      
    case "ToolExecutionCompleted":
      isError = !!details.error
      icon = isError ? <AlertTriangle className="h-3.5 w-3.5 text-destructive" /> : <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
      borderColor = isError ? "border-destructive/40" : "border-emerald-500/40"
      bgClass = isError ? "bg-destructive/5" : "bg-emerald-500/5"
      title = `Tool Completed: ${details.tool_name}`
      const resRaw = details.result || details.error || ""
      content = (
        <div className="space-y-1 mt-1.5">
          <div className="text-[10px] uppercase text-muted-foreground font-semibold">Result:</div>
          <div className={`bg-background border rounded-md p-2 text-[10px] font-mono whitespace-pre-wrap overflow-x-auto ${isError ? 'text-destructive' : 'text-emerald-600 dark:text-emerald-400'}`}>
            {safeStringify(resRaw, expanded)}
          </div>
          {isLongStr(resRaw) && (
            <button onClick={() => setExpanded(!expanded)} className="text-[10px] text-muted-foreground hover:text-foreground flex items-center gap-1 mt-1 cursor-pointer">
              {expanded ? <><ChevronUp className="h-3 w-3"/> Show Less</> : <><ChevronDown className="h-3 w-3"/> Show More</>}
            </button>
          )}
        </div>
      )
      break
      
    case "AgentStepStarted":
      icon = <PlayCircle className="h-3.5 w-3.5 text-primary" />
      borderColor = "border-primary/40"
      title = "Agent Step Started"
      content = <div className="text-[10px] text-muted-foreground mt-1">Agent is thinking...</div>
      break
      
    case "AgentStepCompleted":
      icon = <StopCircle className="h-3.5 w-3.5 text-primary" />
      borderColor = "border-primary/40"
      title = "Agent Step Completed"
      content = (
        <div className="text-[10px] text-muted-foreground mt-1">
          Made <span className="font-semibold text-foreground">{details.tool_calls || 0}</span> tool calls.
        </div>
      )
      break
      
    case "TokenUsageReported":
      icon = <Zap className="h-3.5 w-3.5 text-yellow-500" />
      borderColor = "border-yellow-500/30"
      title = "Tokens Consumed"
      content = (
        <div className="flex gap-3 mt-1.5 text-[10px]">
          <div className="bg-background border rounded px-2 py-1">
            <span className="text-muted-foreground">Prompt:</span> <span className="font-mono">{details.prompt_tokens}</span>
          </div>
          <div className="bg-background border rounded px-2 py-1">
            <span className="text-muted-foreground">Completion:</span> <span className="font-mono">{details.completion_tokens}</span>
          </div>
        </div>
      )
      break
      
    case "WorkflowStarted":
    case "WorkflowCompleted":
    case "WorkflowPaused":
      icon = <Activity className="h-3.5 w-3.5 text-blue-500" />
      borderColor = "border-blue-500/40"
      bgClass = "bg-blue-500/5"
      title = event_type
      content = <div className="text-[10px] text-muted-foreground mt-1 text-xs">Session: {details.session_id}</div>
      break
      
    case "HandoffRequested":
      icon = <ArrowRightLeft className="h-3.5 w-3.5 text-orange-500" />
      borderColor = "border-orange-500/40"
      bgClass = "bg-orange-500/5"
      title = `Handoff: ${details.source_agent_name} → ${details.target_agent_name}`
      content = (
        <div className="mt-1.5 p-2 bg-background border rounded-md text-[10px] text-muted-foreground italic">
          "{details.context_message}"
        </div>
      )
      break
      
    case "SubAgentStarted":
    case "SubAgentCompleted":
      icon = <Network className="h-3.5 w-3.5 text-indigo-500" />
      borderColor = "border-indigo-500/40"
      bgClass = "bg-indigo-500/5"
      title = event_type === "SubAgentStarted" ? `Sub-Agent Started: ${details.sub_agent_name}` : `Sub-Agent Finished: ${details.sub_agent_name}`
      content = details.task_description ? (
        <div className="mt-1.5 p-2 bg-background border rounded-md text-[10px] text-muted-foreground">
          {details.task_description}
        </div>
      ) : details.result ? (
        <div className="mt-1.5 p-2 bg-background border rounded-md text-[10px] text-indigo-600 dark:text-indigo-400 font-mono overflow-x-auto whitespace-pre-wrap">
          {safeStringify(details.result, expanded)}
          {isLongStr(details.result) && (
            <button onClick={() => setExpanded(!expanded)} className="text-[10px] text-muted-foreground hover:text-foreground flex items-center gap-1 mt-1 cursor-pointer">
              {expanded ? <><ChevronUp className="h-3 w-3"/> Show Less</> : <><ChevronDown className="h-3 w-3"/> Show More</>}
            </button>
          )}
        </div>
      ) : null
      break
      
    case "TaskCompletedEvent":
      icon = <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
      borderColor = "border-emerald-500/40"
      title = "Background Task Completed"
      content = (
        <div className="mt-1.5 p-2 bg-background border rounded-md text-[10px] text-muted-foreground font-mono overflow-x-auto whitespace-pre-wrap">
          {safeStringify(details.result, expanded)}
          {isLongStr(details.result) && (
            <button onClick={() => setExpanded(!expanded)} className="text-[10px] text-muted-foreground hover:text-foreground flex items-center gap-1 mt-1 cursor-pointer">
              {expanded ? <><ChevronUp className="h-3 w-3"/> Show Less</> : <><ChevronDown className="h-3 w-3"/> Show More</>}
            </button>
          )}
        </div>
      )
      break
      
    case "HumanApprovalRequested":
      icon = <ShieldCheck className="h-3.5 w-3.5 text-orange-500" />
      borderColor = "border-orange-500/40"
      bgClass = "bg-orange-500/5"
      title = `Approval Requested: ${details.tool_name}`
      break
      
    case "HumanApprovalProvided":
      icon = <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
      borderColor = "border-emerald-500/40"
      bgClass = "bg-emerald-500/5"
      title = `Approval Decision: ${details.result}`
      break
      
    case "GuardrailTriggered":
      icon = <ShieldAlert className="h-3.5 w-3.5 text-destructive" />
      borderColor = "border-destructive/40"
      bgClass = "bg-destructive/5"
      title = `Guardrail Triggered: ${details.action_taken}`
      content = (
        <div className="space-y-1 mt-1.5">
          <div className="text-[10px] text-destructive font-medium">{details.message}</div>
          <div className="text-[10px] text-muted-foreground uppercase mt-2 font-semibold">Stage: {details.stage}</div>
        </div>
      )
      break
      
    case "MemoryReadEvent":
    case "MemoryWrittenEvent":
      icon = <Database className="h-3.5 w-3.5 text-slate-500" />
      borderColor = "border-slate-500/40"
      title = event_type === "MemoryReadEvent" ? "Memory Read" : "Memory Written"
      content = <div className="text-[10px] text-muted-foreground mt-1">{details.message_count ? `Retrieved ${details.message_count} messages` : `Role: ${details.role}`}</div>
      break
      
    case "WorkspaceReadEvent":
    case "WorkspaceWrittenEvent":
      icon = <Save className="h-3.5 w-3.5 text-cyan-500" />
      borderColor = "border-cyan-500/40"
      title = event_type === "WorkspaceReadEvent" ? "Workspace Read" : "Workspace Written"
      content = <div className="text-[10px] text-muted-foreground mt-1">{details.items_retrieved ? `Retrieved ${details.items_retrieved} items` : `Action: ${details.action}`}</div>
      break
      
    case "ToolSearchStarted":
    case "ToolSearchCompleted":
      icon = <Search className="h-3.5 w-3.5 text-pink-500" />
      borderColor = "border-pink-500/40"
      title = event_type === "ToolSearchStarted" ? "Searching Tools" : "Tool Search Completed"
      content = <div className="text-[10px] text-muted-foreground mt-1">{details.query ? `Query: "${details.query}"` : `Found: ${details.tools_found} tools`}</div>
      break
      
    case "ContextCompactionStarted":
    case "ContextCompactionCompleted":
      icon = <FileText className="h-3.5 w-3.5 text-yellow-600" />
      borderColor = "border-yellow-600/40"
      title = event_type === "ContextCompactionStarted" ? "Context Compaction Started" : "Context Compaction Completed"
      content = (
        <div className="text-[10px] text-muted-foreground mt-1">
          {details.current_tokens ? `Tokens: ${details.current_tokens} / ${details.max_tokens}` : `New Tokens: ${details.new_tokens}`}
        </div>
      )
      break
      
    case "ProviderRetrying":
      icon = <Clock3 className="h-3.5 w-3.5 text-orange-500" />
      borderColor = "border-orange-500/40"
      bgClass = "bg-orange-500/5"
      title = `Provider Retrying (Attempt ${details.attempt_number})`
      content = (
        <div className="mt-1.5 p-2 bg-background border border-orange-500/30 rounded-md text-[10px] text-orange-600 dark:text-orange-400 font-mono whitespace-pre-wrap overflow-x-auto">
          {details.error}
          <div className="mt-1 text-muted-foreground">Waiting {details.wait_time_seconds}s...</div>
        </div>
      )
      break
      
    case "Error":
      icon = <AlertTriangle className="h-3.5 w-3.5 text-destructive" />
      borderColor = "border-destructive/40"
      bgClass = "bg-destructive/5"
      title = "System Error"
      content = (
        <div className="mt-1.5 p-2 bg-background border border-destructive/30 rounded-md text-[10px] text-destructive font-mono whitespace-pre-wrap overflow-x-auto">
          {safeStringify(details.content, true)}
        </div>
      )
      break

    default:
      // Fallback
      content = (
        <div className="mt-1.5">
          <pre className="bg-background border rounded-md p-2 text-[10px] overflow-x-auto text-muted-foreground">
            {JSON.stringify(details, null, 2)}
          </pre>
        </div>
      )
      break
  }

  return (
    <div className={`border-l-2 ${borderColor} pl-3 py-1.5 mb-2`}>
      <div className={`rounded-md p-2 ${bgClass}`}>
        <div className="flex items-center justify-between">
          <div className="flex gap-2 items-center">
            {icon}
            <span className="text-foreground text-xs font-semibold tracking-tight">{title}</span>
          </div>
          <span className="text-muted-foreground/60 text-[10px] font-mono whitespace-nowrap ml-2 shrink-0">{timeStr}</span>
        </div>
        {content}
      </div>
    </div>
  )
}
