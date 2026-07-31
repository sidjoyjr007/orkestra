import React, { useState, useEffect } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { PageHeader } from "@/components/PageHeader"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { ArrowLeft, Cpu, Loader2, Terminal, MessageSquare } from "lucide-react"
import { API_BASE_URL } from "@/config"
import { toast } from "sonner"
import Editor from "@monaco-editor/react"

export function TestLlm({ onBack }) {
  const { uuid } = useParams()
  const navigate = useNavigate()
  
  const [llm, setLlm] = useState(null)
  const [loading, setLoading] = useState(true)
  
  const [prompt, setPrompt] = useState("Explain the concept of quantum entanglement in simple terms.")
  const [isExecuting, setIsExecuting] = useState(false)
  
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    const fetchLlm = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/llms`, { credentials: "include" })
        if (res.ok) {
          const data = await res.json()
          const found = data.find(l => l.id === uuid)
          if (found) {
            setLlm(found)
          } else {
            toast.error("LLM not found")
            if (onBack) onBack()
            else navigate("/llms")
          }
        }
      } catch (err) {
        toast.error("Failed to fetch LLM details")
      } finally {
        setLoading(false)
      }
    }
    fetchLlm()
  }, [uuid, navigate, onBack])

  const handleTest = async () => {
    if (!prompt.trim()) {
      toast.error("Please enter a prompt")
      return
    }
    
    setIsExecuting(true)
    setError(null)
    setResult(null)
    
    try {
      const res = await fetch(`${API_BASE_URL}/api/llms/${uuid}/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ prompt })
      })
      
      const data = await res.json()
      
      if (res.ok) {
        setResult(data)
      } else {
        setError(data.detail || "An error occurred during testing")
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setIsExecuting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-muted-foreground gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <p className="text-sm font-medium uppercase tracking-widest">Loading LLM Configuration...</p>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 pb-10">
      <PageHeader
        icon={<Cpu className="h-[18px] w-[18px]" />}
        title="Test LLM"
        description={`Run and debug ${llm?.name} (${llm?.provider} - ${llm?.model_name}).`}
        actions={
          <Button
            variant="ghost"
            size="sm"
            onClick={onBack || (() => navigate("/llms"))}
            className="text-xs text-muted-foreground cursor-pointer"
          >
            <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
            Back to LLM Hub
          </Button>
        }
      />
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Panel: Config & Code */}
        <div className="space-y-6">
          <Card className="p-5 space-y-4 shadow-sm border-border/50">
            <h2 className="text-sm font-semibold tracking-tight text-foreground flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-primary" />
              User Prompt
            </h2>
            
            <div className="rounded-lg overflow-hidden border border-border bg-[#1e1e1e]">
              <Editor
                height="300px"
                language="markdown"
                theme="vs-dark"
                value={prompt}
                onChange={setPrompt}
                options={{
                  minimap: { enabled: false },
                  fontSize: 13,
                  wordWrap: "on",
                  lineNumbers: "off",
                  padding: { top: 12, bottom: 12 },
                }}
              />
            </div>
            
            <Button 
              onClick={handleTest} 
              disabled={isExecuting}
              className="w-full text-xs font-medium h-9 cursor-pointer shadow-sm transition-colors"
            >
              {isExecuting ? (
                <><Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" /> Querying Model...</>
              ) : (
                <><MessageSquare className="h-3.5 w-3.5 mr-2" /> Send Prompt</>
              )}
            </Button>
          </Card>
        </div>
        
        {/* Right Panel: Console */}
        <div className="h-full lg:h-[500px]">
          <Card className="h-full flex flex-col shadow-sm border-border overflow-hidden bg-background">
            <div className="flex items-center gap-2 px-4 py-3 border-b border-border bg-muted/30">
              <Terminal className="h-4 w-4 text-muted-foreground" />
              <span className="text-xs font-mono font-medium text-foreground uppercase tracking-wide">LLM Output</span>
              
              {result && (
                <span className="ml-auto text-[10px] font-mono text-muted-foreground bg-muted/50 px-2 py-0.5 rounded">
                  {result.elapsed_ms}ms
                </span>
              )}
            </div>
            
            <div className="flex-1 p-4 overflow-y-auto">
              {isExecuting ? (
                <div className="flex h-full items-center justify-center">
                  <p className="text-[11px] font-mono text-gray-500 uppercase tracking-widest">Awaiting response...</p>
                </div>
              ) : error ? (
                <pre className="text-xs font-mono text-destructive whitespace-pre-wrap leading-relaxed">
                  {error}
                </pre>
              ) : result ? (
                <pre className="text-xs font-mono text-muted-foreground whitespace-pre-wrap leading-relaxed">
                  {result.content}
                </pre>
              ) : (
                <div className="flex h-full items-center justify-center">
                  <p className="text-[11px] font-mono text-gray-500 uppercase tracking-widest">Waiting for execution...</p>
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
