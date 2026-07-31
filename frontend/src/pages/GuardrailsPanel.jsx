import React, { useState, useEffect } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import {
  Shield,
  Plus,
  ArrowLeft,
  Pencil,
  Trash2,
  PlusCircle,
  Search,
  ShieldCheck,
  Sliders,
  ShieldAlert,
  Info
} from "lucide-react"
import { PageHeader } from "@/components/PageHeader"
import { EntityCard } from "@/components/EntityCard"
import { EmptyState } from "@/components/EmptyState"
import { Pagination } from "@/components/Pagination"
import { CheckboxMultiSelect } from "@/components/CheckboxMultiSelect"
import { Badge } from "@/components/ui/badge"
import Editor from "@monaco-editor/react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { API_BASE_URL } from "@/config"
import { useNavigate, useParams, useLocation } from "react-router-dom"
import { usePermissions } from "@/hooks/usePermissions"

export function GuardrailsPanel() {
  const { canCreateGuardrail, canEditGuardrail, canDeleteGuardrail } = usePermissions()
  const [guardrails, setGuardrails] = useState([])
  const [roleOptions, setRoleOptions] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { uuid } = useParams()

  const isCreate = location.pathname.includes("/create")
  const isEdit = !!uuid
  const showHub = !isCreate && !isEdit

  // Form states
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [stage, setStage] = useState("input")
  const [action, setAction] = useState("block")
  const [handlerType, setHandlerType] = useState("regex")
  const [rules, setRules] = useState("")
  const [allowedRoles, setAllowedRoles] = useState([])
  const [isPublic, setIsPublic] = useState(false)

  // Search & Pagination states
  const [searchQuery, setSearchQuery] = useState("")
  const [hubPage, setHubPage] = useState(1)
  const itemsPerPage = 6

  const fetchGuardrails = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/guardrails?limit=1000`, { credentials: "include" })
      if (res.ok) {
        const data = await res.json()
        setGuardrails(data.items || [])
      }
    } catch (err) {
      console.error("Failed to fetch guardrails:", err)
    }
  }

  useEffect(() => {
    const fetchRoles = async () => {
      try {
        const resRoles = await fetch(`${API_BASE_URL}/api/roles`, { credentials: "include" })
        if (resRoles.ok) {
          const roleData = await resRoles.json()
          setRoleOptions((roleData.items || []).map(r => ({ id: r.name, label: r.name })))
        }
      } catch (err) {
        console.error("Failed to fetch roles:", err)
      }
    }
    fetchGuardrails()
    fetchRoles()
  }, [showHub])

  useEffect(() => {
    if (isEdit) {
      const fetchSingle = async () => {
        try {
          const res = await fetch(`${API_BASE_URL}/api/guardrails/${uuid}`, { credentials: "include" })
          if (res.ok) {
            const data = await res.json()
            setName(data.name || "")
            setDescription(data.description || "")
            setStage(data.stage || "input")
            setAction(data.action || "block")
            setHandlerType(data.handlerType || "regex")
            setRules(data.rules || "")
            setAllowedRoles(data.allowed_roles || [])
            setIsPublic(data.is_public || false)
          }
        } catch (err) {
          console.error("Failed to fetch single guardrail:", err)
        }
      }
      fetchSingle()
    } else if (isCreate) {
      setName("")
      setDescription("")
      setStage("input")
      setAction("block")
      setHandlerType("regex")
      setRules("")
      setAllowedRoles([])
      setIsPublic(false)
    }
  }, [isEdit, isCreate, uuid])

  const filteredGuardrails = guardrails.filter(item =>
    item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    item.description.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const totalPages = Math.ceil(filteredGuardrails.length / itemsPerPage) || 1
  const activePage = Math.min(hubPage, totalPages)
  const paginatedGuardrails = filteredGuardrails.slice((activePage - 1) * itemsPerPage, activePage * itemsPerPage)

  const handleEditClick = (item) => {
    navigate(`/guardrails/edit/${item.id}`)
  }

  const handleCreateClick = () => {
    navigate("/guardrails/create")
  }

  const handleRemove = async (id) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/guardrails/${id}`, {
        method: "DELETE",
        credentials: "include"
      })
      if (res.ok) {
        setGuardrails(prev => prev.filter(g => g.id !== id))
      }
    } catch (err) {
      console.error("Failed to delete guardrail", err)
    }
  }

  const handleSave = async (e) => {
    e.preventDefault()
    if (!name.trim()) return

    const payload = {
      ...(isEdit && { id: uuid }),
      name: name.trim(),
      description: description.trim(),
      stage,
      action,
      handlerType,
      rules,
      allowed_roles: allowedRoles,
      is_public: isPublic
    }
    
    setIsLoading(true)
    try {
      const res = await fetch(`${API_BASE_URL}/api/guardrails${isEdit ? `/${uuid}` : ""}`, {
        method: isEdit ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        credentials: "include"
      })
      
      if (res.ok) {
        navigate("/guardrails")
      }
    } catch (err) {
      console.error("Failed to save guardrail", err)
    } finally {
      setIsLoading(false)
    }
  }

  if (showHub) {
    return (
      <div className="space-y-6 w-full text-left">
        <PageHeader
          icon={<Shield className="h-4 w-4" />}
          title="Guardrails Settings"
          description="Configure your guardrails settings in card format."
          actions={
            <>
              <div className="relative w-56">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Search Guardrails..."
                  value={searchQuery}
                  onChange={e => {
                    setSearchQuery(e.target.value)
                    setHubPage(1)
                  }}
                  className="pl-9 h-9 text-xs"
                />
              </div>
              {canCreateGuardrail && (
                <Button size="sm" onClick={handleCreateClick} className="h-9 text-xs cursor-pointer">
                  <Plus className="h-4 w-4 mr-1.5" /> Create Guardrail
                </Button>
              )}
            </>
          }
        />

        <div className="space-y-6">
          {isLoading ? (
            <div className="p-12 text-center text-sm text-muted-foreground flex flex-col items-center gap-3">
              <div className="h-6 w-6 rounded-full border-2 border-primary border-t-transparent animate-spin"></div>
              Loading guardrails...
            </div>
          ) : filteredGuardrails.length === 0 ? (
            <EmptyState
              icon={<Shield />}
              title={searchQuery ? "No guardrails found" : "No guardrails configured"}
              description={searchQuery ? "No guardrails match your search query." : "You have not created any guardrails yet."}
              action={!searchQuery && canCreateGuardrail ? { label: "Create Guardrail", onClick: handleCreateClick } : undefined}
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {paginatedGuardrails.map(item => (
                <EntityCard
                  key={item.id}
                  icon={<Shield className="h-4 w-4" />}
                  title={item.name}
                  description={item.description}
                  badges={[
                    { label: item.stage.toUpperCase(), icon: <Sliders className="h-3 w-3" />, variant: "outline" },
                    { label: item.action === "block" ? "BLOCK" : "FEEDBACK", icon: <ShieldAlert className="h-3 w-3" />, variant: item.action === "block" ? "destructive" : "secondary" },
                    { label: item.handlerType === "regex" ? "Regex" : "LLM Judge", icon: <ShieldCheck className="h-3 w-3" />, variant: "outline" },
                    { label: item.is_public ? "Public" : "Private", variant: "outline" }
                  ]}
                  onEdit={canEditGuardrail ? () => handleEditClick(item) : undefined}
                  onDelete={canDeleteGuardrail ? () => handleRemove(item.id) : undefined}
                />
              ))}
            </div>
          )}

          {filteredGuardrails.length > itemsPerPage && (
            <Pagination
              currentPage={activePage}
              totalPages={totalPages}
              onPageChange={setHubPage}
              totalItems={filteredGuardrails.length}
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
        icon={isEdit ? <Pencil className="h-[18px] w-[18px]" /> : <PlusCircle className="h-[18px] w-[18px]" />}
        title={isEdit ? `Edit Guardrail: ${name}` : "Create Guardrail"}
        description={isEdit ? "Modify rules, matching methods, and mitigation actions." : "Register a custom guardrail safety rule."}
        actions={
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/guardrails")}
            className="text-xs text-muted-foreground cursor-pointer"
          >
            <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
            Back to List
          </Button>
        }
      />

      <form onSubmit={handleSave} className="space-y-5">
        {/* Card 1: Identity Info */}
        <Card className="p-5 space-y-4">
          <div className="space-y-2">
            <h2 className="text-xs font-semibold text-foreground">Guardrail Name</h2>
            <Input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. Credit Card Detector"
              className="text-sm"
              required
            />
          </div>
          <div className="space-y-2">
            <h2 className="text-xs font-semibold text-foreground">Guardrail Description</h2>
            <Textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Brief summary of safety targets..."
              rows={3}
              className="text-xs resize-none"
            />
          </div>
        </Card>

        {/* Card 2: Configuration */}
        <Card className="p-5 space-y-4">
          <h2 className="text-xs font-semibold text-foreground">Pipeline Stage & Actions</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <label className="text-[11px] font-medium text-muted-foreground uppercase">Stage Placement</label>
              <Select value={stage} onValueChange={setStage}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="input">Input (Developer Prompts)</SelectItem>
                  <SelectItem value="action">Action (Tool Execution)</SelectItem>
                  <SelectItem value="output">Output (Generated Text)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <div className="space-y-2">
              <label className="text-[11px] font-medium text-muted-foreground uppercase">Evaluation Method</label>
              <Select value={handlerType} onValueChange={setHandlerType}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="regex">Regex Pattern</SelectItem>
                  <SelectItem value="llm-as-judge">LLM as a Judge</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-[11px] font-medium text-muted-foreground uppercase">Action on Fail</label>
              <Select value={action} onValueChange={setAction}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="block">Block Execution</SelectItem>
                  <SelectItem value="redact">Redact Content</SelectItem>
                  <SelectItem value="feedback">Provide Feedback (Steer)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </Card>

        {/* Card 3: Rules / Logic */}
        <Card className="p-5 space-y-4 overflow-hidden">
          <h2 className="text-xs font-semibold text-foreground">
            {handlerType === "regex" ? "Regex Pattern" : "LLM Evaluation Prompt"}
          </h2>
          <p className="text-[11px] text-muted-foreground leading-relaxed -mt-1.5 mb-2">
            {handlerType === "regex" 
              ? "Specify the regular expression to match. If a match is found, the guardrail triggers." 
              : "Define the rubric for the LLM judge. The judge evaluates the content and responds with PASS, FAIL, or REDACT."}
          </p>
          <div className="h-48 border rounded-md overflow-hidden bg-card">
            <Editor
              height="100%"
              language={handlerType === "regex" ? "regex" : "markdown"}
              theme="vs-dark"
              value={rules}
              onChange={(val) => setRules(val || "")}
              options={{
                minimap: { enabled: false },
                fontSize: 13,
                wordWrap: "on",
                lineNumbers: "on",
                scrollBeyondLastLine: false,
                padding: { top: 12, bottom: 12 },
              }}
            />
          </div>
        </Card>

        {/* Card 4: Allowed Roles Selection */}
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
            placeholder="Select roles that can access this guardrail (Empty = global access)..."
          />
        </Card>

        {/* Card 5: Global Visibility */}
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
                  <strong>Private</strong> guardrails are only visible to you (and roles selected above). <br/><strong>Public</strong> guardrails can be used by anyone in the workspace.
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

        {/* Form Actions */}
        <div className="flex justify-end gap-2 pb-6">
          <Button type="button" variant="outline" onClick={() => navigate("/guardrails")} className="text-xs h-9 cursor-pointer">
            Cancel
          </Button>
          <Button type="submit" disabled={isLoading} className="text-xs h-9 cursor-pointer px-5">
            {isLoading ? "Saving..." : (isEdit ? "Save Guardrail" : "Create Guardrail")}
          </Button>
        </div>
      </form>
    </div>
  )
}
