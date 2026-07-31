import React, { useState, useEffect } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { PageHeader } from "@/components/PageHeader"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Server, ArrowLeft, Loader2, Play, Wrench } from "lucide-react"
import { toast } from "sonner"
import { API_BASE_URL } from "@/config"
import Editor from "@monaco-editor/react"

export function McpTest({ onBack }) {
  const { uuid } = useParams()
  const navigate = useNavigate()
  
  const [mcp, setMcp] = useState(null)
  const [isFetchingMcp, setIsFetchingMcp] = useState(true)
  const [isExecuting, setIsExecuting] = useState(false)
  const [tools, setTools] = useState([])
  const [errorLog, setErrorLog] = useState("")

  useEffect(() => {
    const fetchMcp = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/mcps`, { credentials: "include" })
        if (res.ok) {
          const data = await res.json()
          const found = data.find(m => m.id === uuid)
          if (found) setMcp(found)
        }
      } catch (err) {
        console.error("Failed to fetch MCPs", err)
      } finally {
        setIsFetchingMcp(false)
      }
    }
    fetchMcp()
  }, [uuid])

  if (isFetchingMcp) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!mcp) {
    return (
      <div className="p-8 text-center text-muted-foreground">
        Server not found.
      </div>
    )
  }

  const handleTest = async () => {
    setIsExecuting(true)
    setErrorLog("")
    setTools([])
    
    try {
      const res = await fetch(`${API_BASE_URL}/api/mcps/${uuid}/test`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json"
        },
        credentials: "include"
      })
      
      const data = await res.json()
      
      if (!res.ok) {
        toast.error("Connection failed")
        setErrorLog(`Error: ${data.detail || "Unknown error"}`)
        return
      }
      
      setTools(data.tools || [])
      toast.success(`Successfully fetched ${data.tools?.length || 0} tools!`)
    } catch (err) {
      toast.error("Failed to connect to MCP server")
      setErrorLog(`System Error: ${err.message}`)
    } finally {
      setIsExecuting(false)
    }
  }

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 pb-10">
      <PageHeader
        icon={<Server className="h-[18px] w-[18px]" />}
        title="Test MCP Server"
        description={`Connect to ${mcp.name} and verify available tools.`}
        actions={
          <Button
            variant="ghost"
            size="sm"
            onClick={onBack || (() => navigate("/mcps"))}
            className="text-xs text-muted-foreground cursor-pointer"
          >
            <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
            Back to MCPs
          </Button>
        }
      />
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Panel: Config & Actions */}
        <div className="space-y-6">
          <Card className="p-5 space-y-4 shadow-sm border-border/50">
            <h2 className="text-sm font-semibold tracking-tight text-foreground flex items-center gap-2">
              <Server className="h-4 w-4 text-primary" />
              Server Connection
            </h2>
            
            <div className="space-y-3 pt-2">
              <div className="space-y-1">
                <p className="text-xs font-medium text-muted-foreground">Endpoint</p>
                <p className="text-sm font-mono text-foreground p-2 bg-muted/50 rounded-md border border-border/50">
                  {mcp.endpoint}
                </p>
              </div>
            </div>
            
            <div className="pt-4 border-t border-border/50 mt-6">
              <Button 
                onClick={handleTest} 
                disabled={isExecuting}
                className="w-full text-xs h-9 cursor-pointer"
              >
                {isExecuting ? (
                  <><Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" /> Connecting...</>
                ) : (
                  <><Play className="h-3.5 w-3.5 mr-2" /> Connect & Fetch Tools</>
                )}
              </Button>
            </div>
          </Card>
        </div>
        
        {/* Right Panel: Output */}
        <div className="space-y-6 lg:h-[calc(100vh-12rem)] flex flex-col">
          <Card className="p-5 flex-1 flex flex-col shadow-sm border-border/50 overflow-hidden">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold tracking-tight text-foreground flex items-center gap-2">
                <Wrench className="h-4 w-4 text-primary" />
                Discovered Tools
              </h2>
              {tools.length > 0 && (
                <span className="text-xs font-medium bg-primary/20 text-primary px-2 py-0.5 rounded-full">
                  {tools.length} available
                </span>
              )}
            </div>
            
            <div className="flex-1 bg-black/90 rounded-md border border-border overflow-hidden flex flex-col font-mono text-xs">
              {errorLog ? (
                <div className="p-4 text-destructive whitespace-pre-wrap overflow-y-auto">
                  {errorLog}
                </div>
              ) : tools.length > 0 ? (
                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                  {tools.map((t, idx) => (
                    <div key={idx} className="space-y-2 pb-4 border-b border-border/50 last:border-0 last:pb-0">
                      <div className="flex items-start justify-between gap-4">
                        <span className="text-green-400 font-semibold">{t.name}</span>
                      </div>
                      {t.description && (
                        <p className="text-muted-foreground whitespace-pre-wrap">{t.description}</p>
                      )}
                      {t.schema && (
                        <div className="mt-2">
                          <p className="text-muted-foreground/50 mb-1">Input Schema:</p>
                          <pre className="text-gray-300 bg-white/5 p-2 rounded overflow-x-auto text-[10px]">
                            {JSON.stringify(t.schema, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex-1 flex items-center justify-center text-muted-foreground/50 p-4 text-center">
                  Click "Connect & Fetch Tools" to discover what this server can do.
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
