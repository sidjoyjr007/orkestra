import React, { useState, useEffect } from "react"
import { useNavigate, useLocation, useParams } from "react-router-dom"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
  Plus,
  Trash2,
  KeyRound,
  ShieldCheck,
  AlertCircle,
  Cpu,
  PlusCircle,
  Pencil,
  ArrowLeft,
  Search,
  Globe,
  Info
} from "lucide-react"
import { PageHeader } from "@/components/PageHeader"
import { EntityCard } from "@/components/EntityCard"
import { EmptyState } from "@/components/EmptyState"
import { Pagination } from "@/components/Pagination"
import { CheckboxMultiSelect } from "@/components/CheckboxMultiSelect"
import Editor from "@monaco-editor/react"
import { toast } from "sonner"
import { API_BASE_URL } from "@/config"
import { usePermissions } from "@/hooks/usePermissions"

export function LlmSettings() {
  const navigate = useNavigate()
  const { canCreateLlm, canEditLlm, canDeleteLlm } = usePermissions()
  const [llms, setLlms] = useState([])
  const [roleOptions, setRoleOptions] = useState([])
  const [loading, setLoading] = useState(true)

  const location = useLocation()
  const { uuid } = useParams()

  const isCreateRoute = location.pathname.includes("/create") || location.pathname.includes("/edit/")
  const [currentPage, setCurrentPage] = useState(isCreateRoute ? "create" : "hub")
  const [editingLlm, setEditingLlm] = useState(null)

  // Form states
  const [llmName, setLlmName] = useState("")
  const [provider, setProvider] = useState("OPENAI")
  const [modelName, setModelName] = useState("")
  const [endpointUrl, setEndpointUrl] = useState("")
  const [headersJson, setHeadersJson] = useState("{\n  \"Content-Type\": \"application/json\"\n}")
  const [apiKey, setApiKey] = useState("")
  const [allowedRoles, setAllowedRoles] = useState([])
  const [isPublic, setIsPublic] = useState(false)

  // Search & Pagination states
  const [searchQuery, setSearchQuery] = useState("")
  const [hubPage, setHubPage] = useState(1)
  const itemsPerPage = 6

  const fetchLlms = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE_URL}/api/llms`, { credentials: "include" })
      if (res.ok) {
        const data = await res.json()
        setLlms(data || [])
      }
      const resRoles = await fetch(`${API_BASE_URL}/api/roles`, { credentials: "include" })
      if (resRoles.ok) {
        const roleData = await resRoles.json()
        setRoleOptions((roleData.items || []).map(r => ({ id: r.name, label: r.name })))
      }
    } catch (err) {
      toast.error("Failed to fetch LLM configurations or roles")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchLlms()
  }, [])

  const filteredLlms = llms.filter(item =>
    item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    item.provider.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const totalPages = Math.ceil(filteredLlms.length / itemsPerPage) || 1
  const activePage = Math.min(hubPage, totalPages)
  const paginatedLlms = filteredLlms.slice((activePage - 1) * itemsPerPage, activePage * itemsPerPage)

  useEffect(() => {
    if (uuid && llms.length > 0) {
      const item = llms.find(m => m.id === uuid)
      if (item) {
        setEditingLlm(item)
        setLlmName(item.name)
        setProvider(item.provider)
        setModelName(item.model_name)
        setEndpointUrl(item.endpoint_url || "")
        setHeadersJson(item.headers ? JSON.stringify(item.headers, null, 2) : "{\n  \"Content-Type\": \"application/json\"\n}")
        setApiKey("") // Never pre-fill secrets for security
        setAllowedRoles(item.allowed_roles || [])
        setIsPublic(item.is_public || false)
        setCurrentPage("create")
      }
    } else if (location.pathname === "/models/create") {
      handleCreateClick(false)
    } else if (location.pathname === "/models") {
      setCurrentPage("hub")
    }
  }, [uuid, llms, location.pathname])

  const handleEditClick = (item) => {
    navigate(`/models/edit/${item.id}`)
  }

  const handleCreateClick = (doNavigate = true) => {
    if (doNavigate) {
      navigate("/models/create")
      return
    }
    setEditingLlm(null)
    setLlmName("")
    setProvider("OPENAI")
    setModelName("gpt-4o")
    setEndpointUrl("")
    setHeadersJson("{\n  \"Content-Type\": \"application/json\"\n}")
    setApiKey("")
    setAllowedRoles([])
    setIsPublic(false)
    setCurrentPage("create")
  }
  
  const handleCancel = () => {
    navigate("/models")
  }

  const handleRemoveLlm = async (id) => {
    if (!window.confirm("Delete this LLM configuration?")) return
    try {
      const res = await fetch(`${API_BASE_URL}/api/llms/${id}`, {
        method: "DELETE",
        credentials: "include"
      })
      if (res.ok) {
        toast.success("LLM deleted")
        fetchLlms()
      } else {
        toast.error("Failed to delete LLM")
      }
    } catch (err) {
      toast.error("Error deleting LLM")
    }
  }

  const handleSave = async (e) => {
    e.preventDefault()
    if (!llmName.trim() || !modelName.trim()) {
      toast.error("Name and Model Name are required")
      return
    }
    
    if (provider === "VLLM" && !endpointUrl.trim()) {
      toast.error("Endpoint URL is required for vLLM providers")
      return
    }

    const payload = {
      name: llmName.trim(),
      provider: provider,
      model_name: modelName.trim(),
      endpoint_url: provider === "VLLM" ? endpointUrl.trim() : null,
      headers: null,
      api_key: apiKey ? apiKey : undefined,
      allowed_roles: allowedRoles,
      is_public: isPublic
    }

    try {
      const isEditing = !!editingLlm
      const res = await fetch(`${API_BASE_URL}/api/llms${isEditing ? `/${editingLlm.id}` : ''}`, {
        method: isEditing ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload)
      })
      
      if (res.ok) {
        toast.success("LLM Configuration saved!")
        fetchLlms()
        navigate("/models")
      } else {
        const errData = await res.json()
        toast.error(errData.detail || "Failed to save configuration")
      }
    } catch (err) {
      toast.error("An error occurred")
    }
  }

  if (currentPage === "hub") {
    return (
      <div className="space-y-6 w-full text-left">
        <PageHeader
          icon={<Cpu className="h-4 w-4" />}
          title="LLM Settings"
          description="Configure your LLMs, AI providers, and endpoints securely."
          actions={
            <>
              <div className="relative w-56">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Search LLMs..."
                  value={searchQuery}
                  onChange={e => {
                    setSearchQuery(e.target.value)
                    setHubPage(1)
                  }}
                  className="pl-9 h-9 text-xs"
                />
              </div>
              {canCreateLlm && (
                <Button size="sm" onClick={handleCreateClick} className="h-9 text-xs cursor-pointer">
                  <Plus className="h-4 w-4 mr-1.5" /> Register LLM
                </Button>
              )}
            </>
          }
        />

        <div className="space-y-6">
          {loading ? (
            <div className="p-12 text-center text-sm text-muted-foreground flex flex-col items-center gap-3">
              <div className="h-6 w-6 rounded-full border-2 border-primary border-t-transparent animate-spin"></div>
              Loading LLMs...
            </div>
          ) : filteredLlms.length === 0 ? (
            <EmptyState
              icon={<Cpu />}
              title={searchQuery ? "No models found" : "No models configured"}
              description={searchQuery ? "No models match your search query." : "You have not registered any custom LLM configurations yet."}
              action={!searchQuery && canCreateLlm ? { label: "Register LLM", onClick: handleCreateClick } : undefined}
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {paginatedLlms.map(item => (
                <EntityCard
                  key={item.id}
                  icon={<Cpu className="h-4 w-4 text-primary" />}
                  title={item.name || "Untitled Config"}
                  description={`Powers agents using the ${item.model_name} model.`}
                  badges={[
                    { label: item.provider, icon: <Globe className="h-3 w-3" />, variant: "default" },
                    { label: item.is_public ? "Public" : "Private", variant: "outline" }
                  ]}
                  footer={
                    <div className="flex items-center gap-1.5 w-full text-[11px] text-muted-foreground truncate">
                      <Globe className="h-3 w-3 flex-shrink-0" />
                      <span className="truncate">{item.endpoint_url || "Default Provider Endpoint"}</span>
                    </div>
                  }
                  onTest={() => navigate(`/llms/test/${item.id}`)}
                  onEdit={canEditLlm ? () => handleEditClick(item) : undefined}
                  onDelete={canDeleteLlm ? () => handleRemoveLlm(item.id) : undefined}
                />
              ))}
            </div>
          )}

          {filteredLlms.length > itemsPerPage && (
            <Pagination
              currentPage={activePage}
              totalPages={totalPages}
              onPageChange={setHubPage}
              totalItems={filteredLlms.length}
              itemsPerPage={itemsPerPage}
            />
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 w-full text-left">
      <PageHeader
        icon={editingLlm ? <Pencil className="h-[18px] w-[18px]" /> : <PlusCircle className="h-[18px] w-[18px]" />}
        title={editingLlm ? `Edit LLM: ${editingLlm.name}` : "Register LLM"}
        description={editingLlm ? "Modify connection details and endpoint properties." : "Register a new customized LLM route endpoint."}
        actions={
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCurrentPage("hub")}
            className="text-xs text-muted-foreground cursor-pointer"
          >
            <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
            Back to Hub
          </Button>
        }
      />

      <form onSubmit={handleSave} className="space-y-5">
        <Card className="p-5 space-y-5">
          <div className="grid grid-cols-2 gap-5">
            <div className="space-y-2">
              <h2 className="text-xs font-semibold text-foreground">Configuration Name</h2>
              <Input
                value={llmName}
                onChange={e => setLlmName(e.target.value)}
                placeholder="e.g. Production GPT-4"
                className="text-sm"
                required
              />
            </div>
            <div className="space-y-2">
              <h2 className="text-xs font-semibold text-foreground">Provider</h2>
              <Select value={provider} onValueChange={(val) => {
                setProvider(val);
                if (val === "OPENAI") setModelName("gpt-4o")
                if (val === "ANTHROPIC") setModelName("claude-3-5-sonnet-20240620")
                if (val === "GEMINI") setModelName("gemini-1.5-pro")
                if (val === "VLLM") setModelName("meta-llama/Llama-3-8b-instruct")
              }}>
                <SelectTrigger className="text-sm h-9">
                  <SelectValue placeholder="Select provider" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="OPENAI">OpenAI</SelectItem>
                  <SelectItem value="ANTHROPIC">Anthropic</SelectItem>
                  <SelectItem value="GEMINI">Google Gemini</SelectItem>
                  <SelectItem value="VLLM">vLLM Server</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          
          <div className="space-y-2">
            <h2 className="text-xs font-semibold text-foreground">Model Name</h2>
            <Input
              value={modelName}
              onChange={e => setModelName(e.target.value)}
              placeholder="e.g. gpt-4o, claude-3-5-sonnet-20240620"
              className="text-sm"
              required
            />
          </div>

          <div className="space-y-2">
            <h2 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
              API Key / Secret Token
              {editingLlm && editingLlm.has_api_key && (
                <span className="text-[10px] text-green-600 bg-green-500/10 px-1.5 py-0.5 rounded ml-2 uppercase font-bold tracking-wider">
                  Configured
                </span>
              )}
            </h2>
            <div className="relative">
              <KeyRound className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                type="password"
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                placeholder={editingLlm && editingLlm.has_api_key ? "Leave blank to keep existing key" : "sk-... enter secret API key"}
                className="text-sm pl-9"
              />
            </div>
            <p className="text-[10px] text-muted-foreground leading-relaxed mt-1.5 max-w-xl">
              API keys are encrypted at rest using AES-256-GCM. 
            </p>
          </div>
        </Card>

        {provider === "VLLM" && (
          <Card className="p-5 space-y-4">
            <div className="flex items-center gap-2 mb-2">
              <ShieldCheck className="h-4 w-4 text-primary" />
              <h2 className="text-sm font-bold tracking-widest uppercase">vLLM Connection</h2>
            </div>
            
            <div className="space-y-2">
              <h2 className="text-xs font-semibold text-foreground">Endpoint URL</h2>
              <Input
                value={endpointUrl}
                onChange={e => setEndpointUrl(e.target.value)}
                placeholder="http://localhost:8000/v1/chat/completions"
                className="text-sm"
                required={provider === "VLLM"}
              />
            </div>
          </Card>
        )}

        <Card className="p-5 space-y-4 !overflow-visible">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold text-foreground">Allowed Roles (Access Control)
              <span className="ml-1 text-[10px] font-normal text-muted-foreground">({allowedRoles.length} selected)</span>
            </h2>
          </div>
          <CheckboxMultiSelect
            options={roleOptions}
            selected={allowedRoles}
            onChange={setAllowedRoles}
            emptyText="No roles available."
            placeholder="Select roles that can access this LLM (Empty = only you)..."
          />
        </Card>

        <Card className="p-5 space-y-4 !overflow-visible">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold text-foreground">Global Visibility</h2>
          </div>
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5 text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
              Visibility
              <div className="relative group flex items-center">
                <Info className="h-3.5 w-3.5 text-muted-foreground/60 cursor-help hover:text-foreground transition-colors" />
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2.5 bg-popover text-popover-foreground text-[11px] leading-relaxed rounded-md shadow-lg border border-border/50 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50 text-center font-normal normal-case">
                  <strong>Private</strong> LLMs are only visible to you (and roles selected above). <br/><strong>Public</strong> LLMs can be used by anyone in the workspace.
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
        </Card>

        <div className="flex justify-end gap-2 pb-6">
          <Button type="button" variant="outline" onClick={handleCancel} className="text-xs h-9 cursor-pointer">
            Cancel
          </Button>
          <Button type="submit" className="text-xs h-9 cursor-pointer px-5">
            Save Configuration
          </Button>
        </div>
      </form>
    </div>
  )
}
