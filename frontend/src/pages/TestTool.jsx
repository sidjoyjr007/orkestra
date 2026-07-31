import React, { useState, useEffect } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { useSelector } from "react-redux"
import { PageHeader } from "@/components/PageHeader"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card } from "@/components/ui/card"
import { Play, Terminal, ArrowLeft, Loader2, FlaskConical } from "lucide-react"
import Editor from "@monaco-editor/react"
import { toast } from "sonner"
import { API_BASE_URL } from "@/config"

export function TestTool({ onBack }) {
  const { uuid } = useParams()
  const navigate = useNavigate()
  const tools = useSelector(state => state.tools?.items || [])
  const tool = tools.find(t => t.id === uuid)
  
  const [paramValues, setParamValues] = useState({})
  const [output, setOutput] = useState("")
  const [isExecuting, setIsExecuting] = useState(false)
  
  useEffect(() => {
    if (tool && tool.params) {
      const initialVals = {}
      tool.params.forEach(p => {
        initialVals[p.name] = p.default || ""
      })
      setParamValues(initialVals)
    }
  }, [tool])

  if (!tool) {
    return (
      <div className="p-8 text-center text-muted-foreground">
        Tool not found.
      </div>
    )
  }

  const handleExecute = async () => {
    setIsExecuting(true)
    setOutput("Executing tool...\n")
    
    try {
      const res = await fetch(`${API_BASE_URL}/api/tools/${tool.id}/execute`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        credentials: "include",
        body: JSON.stringify({ parameters: paramValues })
      })
      
      const data = await res.json()
      
      if (!res.ok) {
        toast.error(data.detail || "Execution failed")
        setOutput(prev => prev + `\nError: ${data.detail || "Unknown error"}`)
        return
      }
      
      setOutput(prev => prev + `\n--- Output ---\n${data.stdout}\n\n--- Errors ---\n${data.stderr}`)
    } catch (err) {
      toast.error("Failed to connect to execution engine")
      setOutput(prev => prev + `\nSystem Error: ${err.message}`)
    } finally {
      setIsExecuting(false)
    }
  }

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 pb-10">
      <PageHeader
        icon={<FlaskConical className="h-[18px] w-[18px]" />}
        title="Test Tool"
        description={`Run and debug ${tool.name} in an isolated container.`}
        actions={
          <Button
            variant="ghost"
            size="sm"
            onClick={onBack || (() => navigate("/tools"))}
            className="text-xs text-muted-foreground cursor-pointer"
          >
            <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
            Back to Tools Hub
          </Button>
        }
      />
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Panel: Config & Code */}
        <div className="space-y-6">
          <Card className="p-5 space-y-4 shadow-sm border-border/50">
            <h2 className="text-sm font-semibold tracking-tight text-foreground flex items-center gap-2">
              <FlaskConical className="h-4 w-4 text-primary" />
              Execution Parameters
            </h2>
            
            {tool.params && tool.params.length > 0 ? (
              <div className="space-y-3">
                {tool.params.map(p => (
                  <div key={p.name} className="space-y-1.5">
                    <label className="text-xs font-medium text-foreground">
                      {p.name} <span className="text-[10px] text-muted-foreground ml-1">({p.type})</span>
                      {p.required && <span className="text-red-500 ml-1">*</span>}
                    </label>
                    <Input
                      value={paramValues[p.name] || ""}
                      onChange={e => setParamValues({...paramValues, [p.name]: e.target.value})}
                      className="text-xs h-9 bg-muted/30"
                      placeholder={p.description || `Enter ${p.name}`}
                    />
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground bg-muted/30 p-3 rounded-md">This tool requires no parameters.</p>
            )}
            
            <Button 
              onClick={handleExecute} 
              disabled={isExecuting}
              className="w-full text-xs font-medium h-9 cursor-pointer shadow-sm transition-colors"
            >
              {isExecuting ? <><Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" /> Executing in Container...</> : <><FlaskConical className="h-3.5 w-3.5 mr-2" /> Execute Tool</>}
            </Button>
          </Card>
          
          <Card className="p-5 space-y-3 shadow-sm border-border/50 overflow-hidden">
             <h2 className="text-sm font-semibold tracking-tight text-foreground">
              Tool Script
            </h2>
            <div className="rounded-lg overflow-hidden border border-border bg-[#1e1e1e]">
              <Editor
                height="300px"
                language="python"
                theme="vs-dark"
                value={tool.script}
                options={{
                  readOnly: true,
                  minimap: { enabled: false },
                  fontSize: 12,
                  fontFamily: "'Geist Mono', 'Fira Code', monospace",
                  scrollBeyondLastLine: false,
                  wordWrap: "on",
                  padding: { top: 12, bottom: 12 }
                }}
              />
            </div>
          </Card>
        </div>
        
        {/* Right Panel: Console */}
        <div className="h-full lg:h-[600px]">
          <Card className="h-full flex flex-col shadow-sm border-border overflow-hidden bg-background">
            <div className="flex items-center gap-2 px-4 py-3 border-b border-border bg-muted/30">
              <Terminal className="h-4 w-4 text-muted-foreground" />
              <span className="text-xs font-mono font-medium text-foreground uppercase tracking-wide">Console Output</span>
            </div>
            
            <div className="flex-1 p-4 overflow-y-auto">
              {output ? (
                <pre className="text-xs font-mono text-muted-foreground whitespace-pre-wrap leading-relaxed">
                  {output}
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
