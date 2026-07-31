import React, { useState, useEffect } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { toast } from "sonner"
import { ArrowLeft, PlusCircle, Pencil, Plus, Trash2, KeyRound, ShieldCheck, AlertCircle, Info } from "lucide-react"
import { PageHeader } from "@/components/PageHeader"
import Editor from "@monaco-editor/react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog"
import { CheckboxMultiSelect } from "@/components/CheckboxMultiSelect"

import { useParams, useNavigate } from "react-router-dom"
import { toolService } from "@/services/toolService"

const PYTHON_TYPES = ["str", "int", "float", "bool", "list", "dict", "Any", "Optional[str]", "Optional[int]"]

const DEFAULT_SCRIPT = `def my_custom_tool(param1: str) -> str:
    """
    Brief description of what this tool does.

    Args:
        param1 (str): Description of param1.

    Returns:
        str: Description of the return value.
    """
    # Reference secrets with {{SECRET_KEY}} syntax
    # Your implementation here
    return f"Result: {param1}"
`

export function CreateTool({ onSave, onBack }) {
  const { uuid } = useParams()
  const navigate = useNavigate()
  const isEdit = !!uuid

  const [toolName, setToolName] = useState("")
  const [toolDesc, setToolDesc] = useState("")
  const [toolType, setToolType] = useState("SANDBOX")
  const [isPublic, setIsPublic] = useState(false)
  const [allowedRoles, setAllowedRoles] = useState([])
  const [roleOptions, setRoleOptions] = useState([])
  const [requiresApproval, setRequiresApproval] = useState(false)
  const [status, setStatus] = useState("DRAFT")
  const [params, setParams] = useState([
    { id: Date.now(), name: "", description: "", type: "str", default: "", required: false }
  ])
  const [script, setScript] = useState(DEFAULT_SCRIPT)
  const [envVars, setEnvVars] = useState([])
  const [loading, setLoading] = useState(isEdit)

  // Fetch tool data from database if editing
  useEffect(() => {
    if (!isEdit) return
    const fetchToolData = async () => {
      try {
        const data = await toolService.list()
        const matched = data.items?.find(item => item.id === uuid)
        if (matched) {
          setToolName(matched.name || "")
          setToolDesc(matched.desc || "")
          setToolType(matched.tool_type || "SANDBOX")
          setIsPublic(matched.is_public || false)
          setAllowedRoles(matched.allowed_roles || [])
          setRequiresApproval(matched.requires_approval || false)
          setStatus(matched.status || "DRAFT")
          setScript(matched.script || "")
          setEnvVars(matched.envVars || [])
          if (matched.params?.length) {
            setParams(matched.params.map((p, idx) => ({ ...p, id: idx })))
          }
        }
      } catch (err) {
        console.error("Failed to load tool metadata", err)
      } finally {
        setLoading(false)
      }
    }
    
    const fetchRoles = async () => {
      try {
        const { apiClient } = await import("@/lib/apiClient")
        const roleData = await apiClient.get("/api/roles")
        setRoleOptions((roleData.items || []).map(r => ({ id: r.name, label: r.name })))
      } catch (err) {
        console.error("Failed to fetch roles:", err)
      }
    }
    
    fetchRoles()
    fetchToolData()
  }, [uuid, isEdit])

  const [showEnvPanel, setShowEnvPanel] = useState(false)
  const [newEnvKey, setNewEnvKey] = useState("")
  const [newEnvValue, setNewEnvValue] = useState("")
  const [envError, setEnvError] = useState("")

  const addEnvVar = () => {
    const key = newEnvKey.trim().toUpperCase().replace(/[^A-Z0-9_]/g, "")
    if (!key) {
      setEnvError("Key is required.")
      return
    }
    if (!newEnvValue.trim()) {
      setEnvError("Value is required.")
      return
    }
    if (envVars.some(ev => ev.key === key)) {
      setEnvError(`Key "${key}" already exists. Delete it first to re-configure.`)
      return
    }
    setEnvVars(prev => [...prev, { key, value: newEnvValue.trim() }])
    setNewEnvKey("")
    setNewEnvValue("")
    setEnvError("")
  }

  const removeEnvVar = (key) => {
    setEnvVars(prev => prev.filter(ev => ev.key !== key))
  }

  const addParam = () => {
    setParams(prev => [
      ...prev,
      { id: Date.now(), name: "", description: "", type: "str", default: "", required: false }
    ])
  }

  const removeParam = (id) => {
    setParams(prev => prev.filter(p => p.id !== id))
  }

  const updateParam = (id, field, value) => {
    setParams(prev => prev.map(p => p.id === id ? { ...p, [field]: value } : p))
  }

  const [error, setError] = useState("")

  const handleSubmit = async (e, forcedStatus = "ACTIVE") => {
    if (e && e.preventDefault) e.preventDefault()
    if (!toolName.trim()) return
    setError("")

    // Validate name format: Alphanumeric and spaces only
    if (!/^[a-zA-Z0-9\s_]+$/.test(toolName.trim())) {
      const errMsg = "Tool name must contain only alphanumeric characters, spaces, and underscores."
      toast.error(errMsg)
      setError(errMsg)
      return
    }

    const toolPayload = {
      ...(isEdit && { id: uuid }),
      name: toolName.trim(),
      desc: toolDesc.trim(),
      params: params.map(p => ({
        name: p.name,
        description: p.description,
        type: p.type,
        default: p.default || "",
        required: !!p.required
      })),
      script,
      envVars,
      tool_type: toolType,
      is_public: isPublic,
      allowed_roles: allowedRoles,
      requires_approval: requiresApproval,
      status: forcedStatus
    }

    try {
      const resData = await toolService.save(toolPayload)
      toast.success("Tool saved successfully!")
      onSave({ ...toolPayload, id: resData.id || toolPayload.id })
      onBack()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="space-y-6 w-full text-left">
      <PageHeader
        icon={isEdit ? <Pencil className="h-[18px] w-[18px]" /> : <PlusCircle className="h-[18px] w-[18px]" />}
        title={isEdit ? `Edit Tool: ${toolName}` : "Create Custom Tool"}
        description={isEdit ? "Update this tool's details, parameters, and script." : "Author a new Python capability and register it into the tools catalog."}
        actions={
          <Button
            variant="ghost"
            size="sm"
            onClick={onBack}
            className="text-xs text-muted-foreground cursor-pointer"
          >
            <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
            Back to Tools Hub
          </Button>
        }
      />

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Row 1: Tool Name + Description in one card */}
        <Card className="p-5 space-y-4">
          <div className="space-y-2">
            <h2 className="text-xs font-semibold text-foreground">Tool Name</h2>
            <Input
              value={toolName}
              onChange={e => setToolName(e.target.value)}
              placeholder="e.g. Fetch Weather Data"
              className="text-sm"
              required
            />
          </div>
          <div className="space-y-2">
            <h2 className="text-xs font-semibold text-foreground">Tool Description
              <span className="ml-1 text-[10px] font-normal text-muted-foreground">(used by LLM to decide when to invoke this tool)</span>
            </h2>
            <Textarea
              value={toolDesc}
              onChange={e => setToolDesc(e.target.value.slice(0, 200))}
              placeholder="Fetches real-time weather for a given city using coordinates..."
              rows={3}
              maxLength={200}
              className="text-xs resize-none"
            />
            <div className="flex justify-end mt-1">
              <span className={`text-[10px] tabular-nums ${toolDesc.length >= 180 ? toolDesc.length >= 200 ? "text-red-500 font-semibold" : "text-amber-500" : "text-muted-foreground"}`}>
                {toolDesc.length} / 200
              </span>
            </div>
            
            <div className="flex items-center gap-8 pt-4 border-t mt-4">
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1.5 text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
                  Environment
                  <div className="relative group flex items-center">
                    <Info className="h-3.5 w-3.5 text-muted-foreground/60 cursor-help hover:text-foreground transition-colors" />
                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-52 p-2.5 bg-popover text-popover-foreground text-[11px] leading-relaxed rounded-md shadow-lg border border-border/50 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50 text-center font-normal normal-case">
                      <strong>Sandbox</strong> executes securely in an isolated container. <br/><strong>Host Machine</strong> executes directly on the server.
                    </div>
                  </div>
                </span>
                <div className="flex bg-muted/60 p-0.5 rounded-md border border-border/50">
                  <button
                    type="button"
                    onClick={() => setToolType("SANDBOX")}
                    className={`text-[11px] px-3 py-1 rounded-sm transition-all cursor-pointer ${toolType === "SANDBOX" ? "bg-background shadow-sm font-medium text-foreground" : "text-muted-foreground hover:text-foreground"}`}
                  >
                    Sandbox
                  </button>
                  <button
                    type="button"
                    onClick={() => setToolType("HOST")}
                    className={`text-[11px] px-3 py-1 rounded-sm transition-all cursor-pointer ${toolType === "HOST" ? "bg-background shadow-sm font-medium text-foreground" : "text-muted-foreground hover:text-foreground"}`}
                  >
                    Host Machine
                  </button>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1.5 text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
                  Visibility
                  <div className="relative group flex items-center">
                    <Info className="h-3.5 w-3.5 text-muted-foreground/60 cursor-help hover:text-foreground transition-colors" />
                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2.5 bg-popover text-popover-foreground text-[11px] leading-relaxed rounded-md shadow-lg border border-border/50 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50 text-center font-normal normal-case">
                      <strong>Private</strong> tools are only visible to you (and roles selected below). <br/><strong>Public</strong> tools can be used by anyone in the workspace.
                    </div>
                  </div>
                </span>
                <div className="flex bg-muted/60 p-0.5 rounded-md border border-border/50">
                  <button
                    type="button"
                    onClick={() => setIsPublic(false)}
                    className={`text-[11px] px-3 py-1 rounded-sm transition-all cursor-pointer ${!isPublic ? "bg-background shadow-sm font-medium text-foreground" : "text-muted-foreground hover:text-foreground"}`}
                  >
                    Private
                  </button>
                  <button
                    type="button"
                    onClick={() => setIsPublic(true)}
                    className={`text-[11px] px-3 py-1 rounded-sm transition-all cursor-pointer ${isPublic ? "bg-background shadow-sm font-medium text-foreground" : "text-muted-foreground hover:text-foreground"}`}
                  >
                    Public (Shared)
                  </button>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1.5 text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
                  Approval
                  <div className="relative group flex items-center">
                    <Info className="h-3.5 w-3.5 text-muted-foreground/60 cursor-help hover:text-foreground transition-colors" />
                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2.5 bg-popover text-popover-foreground text-[11px] leading-relaxed rounded-md shadow-lg border border-border/50 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50 text-center font-normal normal-case">
                      Require human approval before agents can execute this tool.
                    </div>
                  </div>
                </span>
                <div className="flex bg-muted/60 p-0.5 rounded-md border border-border/50">
                  <button
                    type="button"
                    onClick={() => setRequiresApproval(false)}
                    className={`text-[11px] px-3 py-1 rounded-sm transition-all cursor-pointer ${!requiresApproval ? "bg-background shadow-sm font-medium text-foreground" : "text-muted-foreground hover:text-foreground"}`}
                  >
                    Auto
                  </button>
                  <button
                    type="button"
                    onClick={() => setRequiresApproval(true)}
                    className={`text-[11px] px-3 py-1 rounded-sm transition-all cursor-pointer ${requiresApproval ? "bg-background shadow-sm font-medium text-foreground" : "text-muted-foreground hover:text-foreground"}`}
                  >
                    Required
                  </button>
                </div>
              </div>
            </div>
            
            {/* Allowed Roles */}
            <div className="space-y-2 mt-4 pt-4 border-t border-border/50">
              <label className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">Allowed Roles (For Private Tools)</label>
              <div className="max-w-md">
                <CheckboxMultiSelect
                  options={roleOptions}
                  selected={allowedRoles}
                  onChange={setAllowedRoles}
                  placeholder="Select roles that can access this tool..."
                  disabled={isPublic}
                />
              </div>
            </div>
          </div>
        </Card>

        {/* Row 2: Parameters */}
        <Card className="p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xs font-semibold text-foreground">Parameters</h2>
              <p className="text-[11px] text-muted-foreground mt-0.5">Define the inputs your tool function accepts.</p>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={addParam}
              className="text-xs cursor-pointer h-8"
            >
              <Plus className="h-3.5 w-3.5 mr-1.5" /> Add Parameter
            </Button>
          </div>

          {params.length === 0 ? (
            <div className="text-center py-6 border border-dashed rounded-lg">
              <p className="text-xs text-muted-foreground">No parameters defined. Click "Add Parameter" to start.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {/* Header row — 12 cols: 2 name | 4 desc | 2 type | 2 default | 1 required | 1 del */}
              <div className="grid grid-cols-12 gap-2 px-1">
                <span className="col-span-2 text-[10px] font-medium text-muted-foreground uppercase tracking-wide">Name</span>
                <span className="col-span-4 text-[10px] font-medium text-muted-foreground uppercase tracking-wide">Description</span>
                <span className="col-span-2 text-[10px] font-medium text-muted-foreground uppercase tracking-wide">Type</span>
                <span className="col-span-2 text-[10px] font-medium text-muted-foreground uppercase tracking-wide">Default</span>
                <span className="col-span-1 text-[10px] font-medium text-muted-foreground uppercase tracking-wide text-center">Required</span>
                <span className="col-span-1" />
              </div>

              {params.map((param, idx) => (
                <div key={param.id} className="grid grid-cols-12 gap-2 items-center">
                  <div className="col-span-2">
                    <Input
                      value={param.name}
                      onChange={e => updateParam(param.id, "name", e.target.value)}
                      placeholder={`param_${idx + 1}`}
                      className="font-mono text-xs h-8"
                    />
                  </div>
                  <div className="col-span-4">
                    <Input
                      value={param.description}
                      onChange={e => updateParam(param.id, "description", e.target.value)}
                      placeholder="Describe this parameter..."
                      className="text-xs h-8"
                    />
                  </div>
                  <div className="col-span-2">
                    <Select
                      value={param.type}
                      onValueChange={val => updateParam(param.id, "type", val)}
                    >
                      <SelectTrigger className="h-8 text-xs font-mono">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {PYTHON_TYPES.map(t => (
                          <SelectItem key={t} value={t} className="font-mono text-xs">{t}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="col-span-2">
                    <Input
                      value={param.default}
                      onChange={e => updateParam(param.id, "default", e.target.value)}
                      placeholder="None"
                      className="font-mono text-xs h-8"
                    />
                  </div>
                  {/* Required toggle — Checkbox */}
                  <div className="col-span-1 flex justify-center">
                    <button
                      type="button"
                      onClick={() => updateParam(param.id, "required", !param.required)}
                      title={param.required ? "Required" : "Optional"}
                      className={`h-5 w-5 rounded flex items-center justify-center border transition-colors cursor-pointer ${
                        param.required
                          ? "bg-primary border-primary text-primary-foreground"
                          : "border-border bg-background text-muted-foreground hover:border-primary/50"
                      }`}
                    >
                      {param.required && (
                        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                          <path d="M2 5l2.5 2.5L8 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      )}
                    </button>
                  </div>
                  <div className="col-span-1 flex justify-center">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => removeParam(param.id)}
                      className="h-8 w-8 text-muted-foreground hover:text-destructive cursor-pointer"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Row 3: Monaco Script Editor */}
        <Card className="p-5 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xs font-semibold text-foreground">Tool Script</h2>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                Write the Python implementation. Use <span className="font-mono text-primary">{"{{KEY}}"}</span> to reference secrets. The first function defined is automatically set as the entry point.
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setShowEnvPanel(true)
                setEnvError("")
                setNewEnvKey("")
                setNewEnvValue("")
              }}
              className="text-xs cursor-pointer h-8 gap-1.5"
            >
              <KeyRound className="h-3.5 w-3.5" />
              Configure Secrets
              {envVars.length > 0 && (
                <span className="ml-1 inline-flex items-center justify-center h-4 min-w-4 px-1 rounded-full bg-primary/20 text-primary text-[10px] font-semibold">
                  {envVars.length}
                </span>
              )}
            </Button>
          </div>

          <div className="rounded-lg overflow-hidden border border-border">
            <Editor
              height="340px"
              language="python"
              theme="vs-dark"
              value={script}
              onChange={val => setScript(val || "")}
              options={{
                fontSize: 13,
                fontFamily: "'Geist Mono', 'Fira Code', monospace",
                minimap: { enabled: false },
                lineNumbers: "on",
                scrollBeyondLastLine: false,
                wordWrap: "on",
                tabSize: 4,
                automaticLayout: true,
                padding: { top: 14, bottom: 14 },
                scrollbar: { verticalScrollbarSize: 6 },
                renderLineHighlight: "gutter",
                smoothScrolling: true,
              }}
            />
          </div>
        </Card>

        {/* Secrets Dialog */}
        <Dialog open={showEnvPanel} onOpenChange={setShowEnvPanel}>
          <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-sm">
                <ShieldCheck className="h-4 w-4 text-primary" />
                Environment Variables
              </DialogTitle>
              <DialogDescription className="text-xs">
                Add secrets like API keys. Reference them in your script as <span className="font-mono text-primary">{"{{KEY_NAME}}"}</span>. Values are hidden once configured.
              </DialogDescription>
            </DialogHeader>

            {/* Add new secret form */}
            <div className="space-y-2">
              <div className="flex items-end gap-2">
                <div className="flex-1 space-y-1">
                  <label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide">Key</label>
                  <Input
                    value={newEnvKey}
                    onChange={e => {
                      setNewEnvKey(e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, ""))
                      setEnvError("")
                    }}
                    placeholder=""
                    className="font-mono text-xs h-8"
                  />
                </div>
                <div className="flex-1 space-y-1">
                  <label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide">Value</label>
                  <Input
                    type="password"
                    value={newEnvValue}
                    onChange={e => {
                      setNewEnvValue(e.target.value)
                      setEnvError("")
                    }}
                    placeholder=""
                    className="font-mono text-xs h-8"
                  />
                </div>
                <Button
                  type="button"
                  size="sm"
                  onClick={addEnvVar}
                  className="text-xs cursor-pointer h-8 shrink-0"
                >
                  <Plus className="h-3.5 w-3.5 mr-1" /> Add
                </Button>
              </div>
              {envError && (
                <div className="flex items-center gap-1.5 text-[11px] text-red-500">
                  <AlertCircle className="h-3 w-3 shrink-0" />
                  {envError}
                </div>
              )}
            </div>

            {/* Configured secrets list OR empty state */}
            {envVars.length > 0 ? (
              <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
                {envVars.map(ev => (
                  <div key={ev.key} className="flex items-center gap-2 rounded-md border border-border bg-muted/30 px-3 py-2.5">
                    <div className="flex-1 flex items-center gap-3 min-w-0">
                      <span className="font-mono text-xs font-semibold text-foreground shrink-0">{ev.key}</span>
                      <span className="text-muted-foreground text-xs">=</span>
                      <span className="font-mono text-xs text-muted-foreground tracking-widest">••••••••</span>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <span className="text-[9px] text-emerald-500 font-medium uppercase tracking-wide mr-1">Configured</span>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => removeEnvVar(ev.key)}
                        className="h-7 w-7 text-muted-foreground hover:text-destructive cursor-pointer"
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 border border-dashed rounded-lg">
                <div className="relative mb-4">
                  {/* Concentric rings */}
                  <div className="absolute inset-0 -m-4 rounded-full border border-primary/5" />
                  <div className="absolute inset-0 -m-8 rounded-full border border-primary/[0.03]" />
                  <div className="h-10 w-10 rounded-full bg-muted/50 flex items-center justify-center">
                    <KeyRound className="h-5 w-5 text-muted-foreground/60" />
                  </div>
                </div>
                <p className="text-xs font-medium text-muted-foreground">No secrets configured</p>
                <p className="text-[10px] text-muted-foreground/70 mt-1">Add a key-value pair above to get started.</p>
              </div>
            )}

            <DialogFooter>
              <DialogClose render={<Button variant="outline" size="sm" className="text-xs cursor-pointer" />}>Done</DialogClose>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Form Actions */}
        <div className="flex justify-end gap-2 pb-6">
          <Button type="button" variant="outline" onClick={onBack} className="text-xs h-9 cursor-pointer">
            Cancel
          </Button>
          <Button 
            type="button" 
            variant="secondary"
            onClick={(e) => handleSubmit(e, "DRAFT")} 
            className="text-xs h-9 cursor-pointer px-5"
          >
            Save as Draft
          </Button>
          <Button 
            type="button" 
            onClick={(e) => handleSubmit(e, "ACTIVE")} 
            className="text-xs h-9 cursor-pointer px-5"
          >
            {isEdit ? "Update & Publish" : "Save & Publish"}
          </Button>
        </div>
      </form>
    </div>
  )
}
