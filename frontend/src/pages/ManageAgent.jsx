import React, { useState, useEffect, useRef } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { Play, SquareTerminal, Loader2, Send, Bot, User, Activity, Clock, Cpu, BarChart3, Square, Terminal, RefreshCw, ShieldCheck, ArrowLeft } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { PageHeader } from "@/components/PageHeader"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { API_BASE_URL } from "@/config"
import { usePermissions } from "@/hooks/usePermissions"

export function ManageAgent({ agents = [], onBack }) {
  const { id } = useParams()
  const navigate = useNavigate()
  const { canEditAgent } = usePermissions()
  
  const agent = agents.find(a => a.id === id) || { name: "Unknown Agent", id: id }
  
  const [status, setStatus] = useState("LOADING") // LOADING, NOT_DEPLOYED, BUILDING, RUNNING, FAILED, STOPPED
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState("")
  const [isSending, setIsSending] = useState(false)
  const [sessionId] = useState(() => `session-${Date.now()}`)
  const chatContainerRef = useRef(null)
  
  // Telemetry state
  const [runs, setRuns] = useState([])
  const [events, setEvents] = useState([])
  
  // Workspace state
  const [activePlan, setActivePlan] = useState(null)

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/deployments/${id}/status`, { credentials: "include" })
      if (res.ok) {
        const data = await res.json()
        setStatus(data.status)
      } else {
        setStatus("NOT_DEPLOYED")
      }
    } catch (e) {
      console.error(e)
      setStatus("NOT_DEPLOYED")
    }
  }

  const fetchTelemetry = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/telemetry/runs?agent_id=${id}`, { credentials: "include" })
      if (res.ok) {
        const data = await res.json()
        setRuns(data.items || [])
        
        // Fetch events for the most recent run
        if (data.items && data.items.length > 0) {
          const latestRun = data.items[0]
          const evRes = await fetch(`${API_BASE_URL}/api/telemetry/runs/${latestRun.id}/events`, { credentials: "include" })
          if (evRes.ok) {
            const evData = await evRes.json()
            setEvents(evData || [])
          }
        }
      }
    } catch (e) {
      console.error("Failed to fetch telemetry", e)
    }
  }

  const fetchActivePlan = async () => {
    if (status !== "RUNNING") return
    try {
      const res = await fetch(`${API_BASE_URL}/api/workspace/${sessionId}/plan`, { credentials: "include" })
      if (res.ok) {
        const data = await res.json()
        setActivePlan(data.plan)
      }
    } catch (e) {
      console.error("Failed to fetch plan", e)
    }
  }

  useEffect(() => {
    fetchStatus()
    fetchTelemetry()
  }, [id])
  
  // Fetch the active plan initially if running
  useEffect(() => {
    if (status === "RUNNING") {
      fetchActivePlan()
    }
  }, [status, sessionId])
  
  const handleRefresh = () => {
    fetchStatus()
    fetchTelemetry()
    fetchActivePlan()
  }

  const handleDeploy = async () => {
    setStatus("BUILDING")
    try {
      const res = await fetch(`${API_BASE_URL}/api/deployments/${id}/deploy`, {
        method: "POST",
        credentials: "include"
      })
      if (res.ok) {
        fetchStatus()
      } else {
        setStatus("FAILED")
      }
    } catch (e) {
      setStatus("FAILED")
    }
  }
  
  const handleStop = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/deployments/${id}/stop`, {
        method: "POST",
        credentials: "include"
      })
      if (res.ok) {
        fetchStatus()
      }
    } catch (e) {
      console.error("Failed to stop", e)
    }
  }

  const handleSend = async (overrideMsg = undefined) => {
    if (overrideMsg === undefined) {
      if (!input.trim() || isSending) return
    }
    const userMsg = overrideMsg === undefined ? input.trim() : overrideMsg
    if (overrideMsg === undefined) setInput("")
    if (userMsg) {
      setMessages(prev => [...prev, { role: "user", content: userMsg }])
    }
    setActivePlan(null)
    setIsSending(true)

    try {
      const res = await fetch(`${API_BASE_URL}/api/deployments/${id}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ message: userMsg, session_id: sessionId })
      })

      if (!res.ok) {
        setMessages(prev => [...prev, { role: "system", content: "Error: Failed to reach agent." }])
        setIsSending(false)
        return
      }

      if (!userMsg) {
         // If we are just resuming the agent (no user input), we don't need a payload message
      }

      // Add a placeholder message for the assistant if not already present
      setMessages(prev => {
        const last = prev[prev.length - 1]
        if (last && last.role === "assistant") {
          return prev
        }
        return [...prev, { role: "assistant", content: "" }]
      })

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let done = false

      let buffer = ""
      while (!done) {
        const { value, done: doneReading } = await reader.read()
        done = doneReading
        if (value) {
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split("\n")
          // Keep the last partial line in the buffer
          buffer = lines.pop() || ""

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const dataStr = line.substring(6)
              try {
                const eventData = JSON.parse(dataStr)
                if (eventData.event_type === "FinalResponse") {
                  setMessages(prev => {
                    const newMessages = [...prev]
                    const lastIndex = newMessages.length - 1
                    const lastMsg = { ...newMessages[lastIndex] } // Deep copy to prevent React StrictMode double-mutation
                    const current = lastMsg.content || ""
                    const reply = eventData.details.content || ""
                    if (current.includes("[Executing")) {
                       lastMsg.content = reply ? (current + "\n\n" + reply) : current
                    } else {
                       lastMsg.content = reply
                    }
                    
                    newMessages[lastIndex] = lastMsg
                    return newMessages
                  })
                } else if (eventData.event_type === "ToolExecutionStarted") {
                  const toolName = eventData.details.tool_name
                  setMessages(prev => {
                    const newMessages = [...prev]
                    const lastIndex = newMessages.length - 1
                    const lastMsg = { ...newMessages[lastIndex] }
                    const currentContent = lastMsg.content
                    
                    // Use a more stable UI marker for tools
                    const marker = `⏳ *[Executing ${toolName}...]*`
                    lastMsg.content = currentContent ? (currentContent + "\n" + marker) : marker
                    
                    newMessages[lastIndex] = lastMsg
                    newMessages[lastIndex] = lastMsg
                    return newMessages
                  })
                } else if (eventData.event_type === "PausedForApproval") {
                  setMessages(prev => [...prev, {
                    role: "system_hitl",
                    hitl_id: eventData.details.hitl_id,
                    tool_name: eventData.details.tool_name,
                    tool_args: eventData.details.tool_args
                  }])
                } else if (eventData.event_type === "Error") {
                  setMessages(prev => [...prev, { role: "system", content: eventData.details.content }])
                } else if (eventData.event_type === "WorkspaceWrittenEvent") {
                  fetchActivePlan()
                }
              } catch (e) {
                console.error("Failed to parse SSE JSON", e)
              }
            }
          }
        }
      }
    } catch (e) {
      setMessages(prev => [...prev, { role: "system", content: "Network error communicating with agent." }])
    } finally {
      setIsSending(false)
      setIsSending(false)
      fetchTelemetry() // trigger instant telemetry refresh
    }
  }

  const handleHitlRespond = async (hitlId, action, responseText = null) => {
    try {
      // Optimistically remove the widget
      setMessages(prev => prev.filter(m => m.hitl_id !== hitlId))
      
      const res = await fetch(`${API_BASE_URL}/api/hitl/${hitlId}/respond`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ action, response_text: responseText })
      })
      
      if (res.ok) {
        // Resume the agent with no new message
        handleSend(null)
      } else {
        const errText = await res.text().catch(() => "Unknown backend error")
        setMessages(prev => [...prev, { role: "system", content: `Failed to respond to approval request: ${res.status} ${errText}` }])
      }
    } catch (e) {
      setMessages(prev => [...prev, { role: "system", content: `Network error submitting approval: ${e.message || String(e)}` }])
    }
  }

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight
    }
  }, [messages])

  const getStatusBadge = () => {
    switch (status) {
      case "RUNNING": return <Badge className="bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20">Running</Badge>
      case "BUILDING": return <Badge variant="secondary" className="text-blue-500 animate-pulse">Deploying...</Badge>
      case "FAILED": return <Badge variant="destructive">Failed</Badge>
      case "STOPPED": return <Badge variant="outline">Stopped</Badge>
      case "NOT_DEPLOYED": return <Badge variant="outline" className="text-muted-foreground">Not Deployed</Badge>
      default: return <Badge variant="outline" className="animate-pulse">Loading...</Badge>
    }
  }
  
  // Calculate metrics
  const activeExecutions = runs.filter(r => r.status === "IN_PROGRESS").length
  const totalRuns = runs.length
  const tokensConsumed = runs.reduce((acc, r) => acc + (r.total_tokens || 0), 0)

  return (
    <div className="flex flex-col text-left space-y-6 pb-12">
      <PageHeader
        icon={<Terminal className="h-4 w-4" />}
        title={`Manage: ${agent.name}`}
        description={
          <div className="flex items-center gap-2 mt-0.5">
            <span>Agent ID: {id}</span>
            <span className="text-muted-foreground/30">•</span>
            {getStatusBadge()}
          </div>
        }
        actions={
          <div className="flex items-center gap-2">
            {status === "RUNNING" && canEditAgent ? (
              <Button variant="destructive" size="sm" onClick={handleStop}>
                <Square className="h-3.5 w-3.5 mr-1.5 fill-current" /> Stop
              </Button>
            ) : (status === "STOPPED" || status === "NOT_DEPLOYED") && canEditAgent ? (
              <Button size="sm" onClick={handleDeploy}>
                <Play className="h-3.5 w-3.5 mr-1.5 fill-current" /> Deploy
              </Button>
            ) : null}
            <Button variant="outline" size="sm" onClick={handleRefresh}>
              <RefreshCw className="h-3.5 w-3.5 mr-1.5" /> Refresh
            </Button>
            <Button variant="ghost" size="sm" onClick={onBack} className="text-xs text-muted-foreground cursor-pointer">
              <ArrowLeft className="h-3.5 w-3.5 mr-1.5" /> Back to Agents
            </Button>
          </div>
        }
      />
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1">
        
        {/* Chat Console */}
        <div className="lg:col-span-2 flex flex-col border rounded-xl overflow-hidden bg-background shadow-sm relative shrink-0" style={{ height: "600px" }}>
          {/* Internal Pane Header */}
          <div className="px-4 py-3 border-b bg-muted/20 flex items-center justify-between z-20 relative">
            <span className="text-sm font-semibold text-muted-foreground flex items-center gap-2">
              <SquareTerminal className="h-4 w-4" /> Interactive Console
            </span>
          </div>

          <div className="flex-1 relative flex flex-col overflow-hidden">
            {status !== "RUNNING" && (
              <div className="absolute inset-0 z-10 bg-background/95 backdrop-blur-sm flex items-center justify-center">
              <div className="text-center space-y-3">
                <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
                  {status === "BUILDING" ? (
                    <Loader2 className="h-5 w-5 text-primary animate-spin" />
                  ) : (
                    <Bot className="h-5 w-5 text-primary" />
                  )}
                </div>
                <div>
                  <h3 className="font-semibold text-sm">Agent Not Running</h3>
                  <p className="text-xs text-muted-foreground max-w-[200px] mt-1 mx-auto">
                    {status === "BUILDING" 
                      ? "Deploying container..." 
                      : canEditAgent 
                        ? "Deploy the agent to start interacting." 
                        : "Ask an administrator or developer to deploy this agent."}
                  </p>
                </div>
                {status !== "BUILDING" && canEditAgent && (
                  <Button size="sm" onClick={handleDeploy}>Deploy Agent</Button>
                )}
              </div>
            </div>
          )}
          
          <div className="flex-1 overflow-y-auto p-6 space-y-6" ref={chatContainerRef}>
            {messages.length === 0 && status === "RUNNING" && (
              <div className="h-full flex items-center justify-center text-muted-foreground">
                <div className="text-center">
                  <Bot className="h-8 w-8 mx-auto opacity-20 mb-3" />
                  <p className="text-sm font-medium">Session initialized</p>
                  <p className="text-xs opacity-60">Send a message to begin.</p>
                </div>
              </div>
            )}
            {messages.map((m, i) => {
              const renderMessageContent = (content, isToolActive) => {
                if (!content) return null;
                const toolRegex = /⏳ \*\[Executing (.*?)\.\.\.\]\*/g;
                const toolNames = [];
                let match;
                
                while ((match = toolRegex.exec(content)) !== null) {
                  toolNames.push(match[1]);
                }
                
                const cleanContent = content.replace(toolRegex, "").trim();
                
                return (
                  <div className="space-y-2">
                    {toolNames.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 p-0.5 select-none mb-1">
                        {toolNames.map((toolName, idx) => {
                          const isLast = idx === toolNames.length - 1;
                          const active = isLast && isToolActive;
                          return (
                            <div key={idx} className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md border border-border bg-background/50 text-[10px] text-muted-foreground font-medium">
                              {active ? (
                                <span className="flex h-1.5 w-1.5 relative">
                                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary/70 opacity-75"></span>
                                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-primary"></span>
                                </span>
                              ) : (
                                <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/35 shrink-0" />
                              )}
                              <span>{active ? "Running" : "Ran"}: <code className="font-mono text-foreground font-semibold">{toolName}</code></span>
                            </div>
                          );
                        })}
                      </div>
                    )}
                    {cleanContent && (
                      <div className="whitespace-pre-wrap leading-relaxed">
                        {cleanContent}
                      </div>
                    )}
                  </div>
                );
              };

              if (m.role === "system_hitl") {
                return (
                  <div key={i} className="flex justify-start w-full">
                    <div className="w-full max-w-lg rounded-xl border border-border bg-card p-4 shadow-sm animate-in fade-in slide-in-from-bottom-2 duration-200">
                      <div className="flex items-center gap-2 mb-3">
                        <ShieldCheck className="h-4 w-4 text-primary" />
                        <span className="text-xs font-bold uppercase tracking-wider text-foreground">
                          Human Approval Required
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground mb-3 leading-relaxed">
                        The agent is requesting permission to execute <code className="px-1.5 py-0.5 rounded bg-muted font-mono text-xs text-foreground font-semibold">{m.tool_name}</code> with these arguments:
                      </p>
                      <pre className="bg-muted border border-border/40 p-3 rounded-lg text-xs font-mono mb-4 overflow-x-auto text-foreground max-h-60">
                        {JSON.stringify(m.tool_args, null, 2)}
                      </pre>
                      <div className="flex gap-2">
                        <Button 
                          size="sm" 
                          variant="default"
                          onClick={() => handleHitlRespond(m.hitl_id, "APPROVE")}
                        >
                          Approve
                        </Button>
                        <Button 
                          size="sm" 
                          variant="outline" 
                          className="hover:bg-destructive/10 hover:text-destructive hover:border-destructive/30"
                          onClick={() => handleHitlRespond(m.hitl_id, "REJECT")}
                        >
                          Reject
                        </Button>
                      </div>
                    </div>
                  </div>
                )
              }
              
              return (
                <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  {m.role !== 'user' && (
                    <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                      {m.role === 'system' ? <SquareTerminal className="h-4 w-4 text-primary" /> : <Bot className="h-4 w-4 text-primary" />}
                    </div>
                  )}
                  <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${
                    m.role === 'user' ? 'bg-primary text-primary-foreground rounded-tr-sm' : 
                    m.role === 'system' ? 'bg-destructive/10 text-destructive rounded-tl-sm' : 
                    'bg-muted rounded-tl-sm'
                  }`}>
                    {m.content?.trim() ? renderMessageContent(m.content, i === messages.length - 1 && isSending) : (
                      <div className="flex items-center gap-1 py-1.5 px-0.5 select-none">
                        <span className="h-1.5 w-1.5 rounded-full bg-foreground/40 animate-bounce" style={{ animationDelay: "0ms" }} />
                        <span className="h-1.5 w-1.5 rounded-full bg-foreground/40 animate-bounce" style={{ animationDelay: "150ms" }} />
                        <span className="h-1.5 w-1.5 rounded-full bg-foreground/40 animate-bounce" style={{ animationDelay: "300ms" }} />
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
          
          <div className="p-4 border-t bg-background mt-auto">
            <div className="relative border rounded-2xl bg-background shadow-xs focus-within:ring-2 focus-within:ring-primary/20 focus-within:border-primary/50 transition-all p-2 flex flex-col gap-2">
              <textarea
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault()
                    if (input.trim() && !isSending && status === "RUNNING") {
                      handleSend()
                    }
                  }
                }}
                placeholder="Message your agent..."
                disabled={isSending || status !== "RUNNING"}
                className="w-full min-h-[60px] max-h-[160px] resize-none bg-transparent px-3 py-2 text-sm outline-none border-0 focus:ring-0 focus-visible:ring-0 placeholder:text-muted-foreground"
                rows={2}
              />
              <div className="flex items-center justify-between px-3 pb-1">
                <div className="text-[10px] text-muted-foreground/60 select-none">
                  {status === "RUNNING" ? "Press Enter to send, Shift+Enter for new line" : "Agent offline"}
                </div>
                <Button
                  size="icon"
                  className="h-8 w-8 rounded-full bg-foreground text-background hover:bg-foreground/90 shrink-0 cursor-pointer shadow-xs"
                  onClick={handleSend}
                  disabled={isSending || !input.trim() || status !== "RUNNING"}
                >
                  {isSending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                </Button>
              </div>
            </div>
          </div>
        </div>
        </div>
        
        {/* Active Plan Sidebar */}
        <div className="flex flex-col border rounded-xl overflow-hidden bg-background shadow-sm relative shrink-0" style={{ height: "600px" }}>
          <div className="px-4 py-3 border-b bg-muted/20 flex items-center justify-between z-20 relative">
            <span className="text-sm font-semibold text-muted-foreground flex items-center gap-2">
              <Activity className="h-4 w-4" /> Agent Workspace Plan
            </span>
            {activePlan && activePlan.status === "ACTIVE" && (
              <Badge variant="outline" className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20">Active</Badge>
            )}
          </div>
          <div className="flex-1 overflow-y-auto p-4 bg-muted/5">
            {!activePlan ? (
              <div className="h-full flex flex-col items-center justify-center text-muted-foreground opacity-60">
                <Square className="h-8 w-8 mb-3 opacity-50" />
                <p className="text-sm font-medium">No active plan</p>
                <p className="text-xs text-center mt-1 px-4">The agent will create a plan here when breaking down complex tasks.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {activePlan.tasks.map((task, idx) => (
                  <div key={idx} className={`p-3 rounded-lg border ${
                    task.status === "DONE" ? "bg-muted/50 border-muted opacity-70" :
                    task.status === "IN_PROGRESS" ? "bg-primary/5 border-primary/20 shadow-sm" :
                    task.status === "BLOCKED" ? "bg-destructive/5 border-destructive/20" :
                    "bg-background"
                  }`}>
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5">
                        {task.status === "DONE" ? (
                          <div className="h-4 w-4 rounded-full bg-primary flex items-center justify-center text-[10px] text-primary-foreground font-bold">✓</div>
                        ) : task.status === "IN_PROGRESS" ? (
                          <Loader2 className="h-4 w-4 text-primary animate-spin" />
                        ) : (
                          <div className="h-4 w-4 rounded-full border-2 border-muted-foreground" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className={`text-sm font-medium ${task.status === "DONE" ? "line-through text-muted-foreground" : ""}`}>
                          {task.description}
                        </p>
                        {task.notes && (
                          <p className="text-xs text-muted-foreground mt-1 bg-background p-1.5 rounded border">
                            {task.notes}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
      
      {/* Metrics */}
      <div className="w-full">
          <Card className="shadow-sm border rounded-xl overflow-hidden">
            <CardHeader className="pb-2 border-b bg-muted/20">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-muted-foreground" /> Telemetry Metrics
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0 p-0 flex flex-col md:flex-row">
              <div className="flex-1 p-6 text-center border-b md:border-b-0 md:border-r flex flex-col items-center justify-center">
                <div className="text-[10px] uppercase text-muted-foreground font-semibold tracking-wider mb-2 flex items-center justify-center gap-1">
                  <Cpu className="h-3 w-3" /> Active Execs
                </div>
                <div className="text-4xl font-bold font-mono">{activeExecutions}</div>
              </div>
              <div className="flex-1 p-6 text-center border-b md:border-b-0 md:border-r flex flex-col items-center justify-center">
                <div className="text-[10px] uppercase text-muted-foreground font-semibold tracking-wider mb-2 flex items-center justify-center gap-1">
                  <Clock className="h-3 w-3" /> Total Runs
                </div>
                <div className="text-4xl font-bold font-mono">{totalRuns}</div>
              </div>
              <div className="flex-1 p-6 text-center bg-muted/10 relative overflow-hidden flex flex-col items-center justify-center">
                <div className="text-[10px] uppercase text-muted-foreground font-semibold tracking-wider mb-2">Total Tokens Consumed</div>
                <div className="text-4xl font-extrabold font-mono text-foreground">{tokensConsumed}</div>
              </div>
            </CardContent>
          </Card>
        </div>
        
        {/* Live Event Log */}
      <Card className="shadow-sm border rounded-xl overflow-hidden bg-card text-card-foreground flex flex-col shrink-0" style={{ height: "500px" }}>
        <div className="px-4 py-3 border-b bg-muted/20 flex items-center justify-between shrink-0">
          <CardTitle className="text-sm font-semibold text-foreground flex items-center gap-2">
             <SquareTerminal className="h-4 w-4 text-muted-foreground" /> Live Event Log
          </CardTitle>
        </div>
        <CardContent className="p-0 flex-1 overflow-y-auto">
          <div className="w-full">
            <div className="p-4 font-mono text-[12px] leading-relaxed space-y-3">
              {events.length === 0 ? (
                <span className="opacity-50 flex items-center gap-2 text-muted-foreground">
                  No events to display. Refresh to check.
                </span>
              ) : (
                [...events].reverse().map((e, idx) => (
                  <div key={idx} className="border-l-[2px] border-primary/20 pl-3 py-0.5">
                    <div className="flex gap-3 items-center">
                      <span className="text-muted-foreground text-[10px]">[{new Date(e.timestamp).toLocaleTimeString()}]</span>
                      <span className="text-foreground font-semibold tracking-tight">{e.event_type}</span>
                    </div>
                    {e.details && Object.keys(e.details).length > 0 && (
                      <div className="mt-1 whitespace-pre-wrap text-[11px] text-muted-foreground/80 overflow-x-auto">
                        {JSON.stringify(e.details, null, 2)}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
