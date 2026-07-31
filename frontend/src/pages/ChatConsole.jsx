import React, { useState, useEffect, useRef } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { Play, SquareTerminal, Loader2, Send, Bot, User, ShieldCheck } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { PageHeader } from "@/components/PageHeader"
import { API_BASE_URL } from "@/config"

export function ChatConsole() {
  const { uuid } = useParams()
  const navigate = useNavigate()
  const [status, setStatus] = useState("LOADING") // LOADING, NOT_DEPLOYED, BUILDING, RUNNING, FAILED
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState("")
  const [isSending, setIsSending] = useState(false)
  const [sessionId] = useState(() => `session-${Date.now()}`)
  const messagesEndRef = useRef(null)

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/deployments/${uuid}/status`, {
        credentials: "include"
      })
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

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(() => {
      if (status === "BUILDING") {
        fetchStatus()
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [uuid, status])

  const handleDeploy = async () => {
    setStatus("BUILDING")
    try {
      const res = await fetch(`${API_BASE_URL}/api/deployments/${uuid}/deploy`, {
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

  const handleSend = async (overrideMsg = undefined) => {
    // If overrideMsg is explicitly null, it means we're resuming without a user message.
    if (overrideMsg === undefined) {
      if (!input.trim() || isSending) return
    }
    
    const userMsg = overrideMsg === undefined ? input.trim() : overrideMsg
    if (overrideMsg === undefined) setInput("")
    
    if (userMsg) {
      setMessages(prev => [...prev, { role: "user", content: userMsg }])
    }
    setIsSending(true)

    try {
      const payload = { session_id: sessionId }
      if (userMsg) payload.message = userMsg

      const res = await fetch(`${API_BASE_URL}/api/deployments/${uuid}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload)
      })
      if (res.ok) {
        const data = await res.json()
        if (data.status === "PAUSED_FOR_APPROVAL") {
          setMessages(prev => [...prev, { 
            role: "system_hitl", 
            hitl_id: data.hitl_id, 
            tool_name: data.tool_name, 
            tool_args: data.tool_args 
          }])
        } else {
          setMessages(prev => [...prev, { role: "assistant", content: data.response }])
        }
      } else {
        setMessages(prev => [...prev, { role: "system", content: "Error: Failed to reach agent." }])
      }
    } catch (e) {
      setMessages(prev => [...prev, { role: "system", content: "Network error communicating with agent." }])
    } finally {
      setIsSending(false)
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
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  return (
    <div className="h-full flex flex-col text-left">
      <PageHeader
        icon={<SquareTerminal className="h-4 w-4" />}
        title="Agent Console"
        description={`Interact with isolated agent deployment: ${uuid}`}
        actions={
          <Button variant="outline" size="sm" onClick={() => navigate("/profile")} className="h-9 text-xs">
            Back to Hub
          </Button>
        }
      />

      <div className="flex-1 flex items-center justify-center p-6 min-h-0 overflow-hidden">
        {status === "LOADING" && <Loader2 className="h-8 w-8 animate-spin text-primary" />}
        
        {(status === "NOT_DEPLOYED" || status === "FAILED" || status === "STOPPED") && (
          <div className="text-center space-y-4">
            <Bot className="h-12 w-12 mx-auto text-muted-foreground/50" />
            <h3 className="text-lg font-bold">Agent Not Deployed</h3>
            <p className="text-sm text-muted-foreground max-w-md">
              This agent is currently inactive or stopped. Deploy it to a secure, isolated container to start chatting.
            </p>
            <Button onClick={handleDeploy} className="gap-2">
              <Play className="h-4 w-4 fill-current" /> Deploy Agent Container
            </Button>
          </div>
        )}

        {status === "BUILDING" && (
          <div className="text-center space-y-4">
            <Loader2 className="h-12 w-12 mx-auto animate-spin text-primary" />
            <h3 className="text-lg font-bold">Bootstrapping Container...</h3>
            <p className="text-sm text-muted-foreground">
              Orkestra is securely injecting configurations and spinning up an isolated runner.
            </p>
          </div>
        )}

        {status === "RUNNING" && (
          <div className="w-full max-w-4xl h-full flex flex-col border rounded-xl overflow-hidden shadow-sm bg-background">
            <div className="bg-muted/50 p-3 border-b flex items-center gap-3">
              <div className="h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs font-bold uppercase tracking-wider">Container Active & Proxying</span>
              <div className="ml-auto flex items-center gap-1.5 text-emerald-500 text-xs font-semibold">
                <ShieldCheck className="h-4 w-4" /> Secure Isolation
              </div>
            </div>
            
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 && (
                <div className="h-full flex flex-col items-center justify-center text-muted-foreground space-y-3">
                  <Bot className="h-10 w-10 opacity-50" />
                  <p className="text-sm font-medium">Session initialized. Send a prompt to the isolated agent.</p>
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
              {isSending && (
                <div className="flex justify-start">
                  <div className="bg-muted border rounded-2xl px-4 py-3">
                    <Loader2 className="h-4 w-4 animate-spin" />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

             <div className="p-4 border-t bg-muted/20">
              <div className="relative border rounded-2xl bg-background shadow-xs focus-within:ring-2 focus-within:ring-primary/20 focus-within:border-primary/50 transition-all p-2 flex flex-col gap-2">
                <textarea
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault()
                      if (input.trim() && !isSending) {
                        handleSend()
                      }
                    }
                  }}
                  placeholder="Type a message to the agent..."
                  className="w-full min-h-[60px] max-h-[160px] resize-none bg-transparent px-3 py-2 text-sm outline-none border-0 focus:ring-0 focus-visible:ring-0 placeholder:text-muted-foreground"
                  disabled={isSending}
                  rows={2}
                />
                <div className="flex items-center justify-between px-3 pb-1">
                  <div className="text-[10px] text-muted-foreground/60 select-none">
                    Press Enter to send, Shift+Enter for new line
                  </div>
                  <Button
                    size="icon"
                    className="h-8 w-8 rounded-full bg-foreground text-background hover:bg-foreground/90 shrink-0 cursor-pointer shadow-xs"
                    onClick={handleSend}
                    disabled={isSending || !input.trim()}
                  >
                    {isSending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
