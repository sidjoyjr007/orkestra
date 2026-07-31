import React, { useState, useEffect } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Plus,
  Trash2,
  KeyRound,
  ShieldCheck,
  AlertCircle,
  Server,
  PlusCircle,
  Pencil,
  ArrowLeft,
  Search,
  Globe,
  Lock,
  Info
} from "lucide-react"
import { PageHeader } from "@/components/PageHeader"
import { EntityCard } from "@/components/EntityCard"
import { Checkbox } from "@/components/ui/checkbox"
import { EmptyState } from "@/components/EmptyState"
import { Pagination } from "@/components/Pagination"
import { CheckboxMultiSelect } from "@/components/CheckboxMultiSelect"
import { useParams, useLocation, useNavigate } from "react-router-dom"
import Editor from "@monaco-editor/react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog"
import { usePermissions } from "@/hooks/usePermissions"
import { API_BASE_URL } from "@/config"

export function McpSettings() {
  const { canCreateMcp, canEditMcp, canDeleteMcp } = usePermissions()
  const [mcps, setMcps] = useState([])
  const [roleOptions, setRoleOptions] = useState([])
  const navigate = useNavigate()

  React.useEffect(() => {
    const fetchMcps = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/mcps`, { credentials: "include" })
        if (res.ok) {
          const data = await res.json()
          setMcps(data)
        }
      } catch (err) {
        console.error("Failed to fetch MCPs", err)
      }
    }
    const fetchRoles = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/roles`, { credentials: "include" })
        if (res.ok) {
          const data = await res.json()
          setRoleOptions((data.items || []).map(r => ({ id: r.name, label: r.name })))
        }
      } catch (err) {
        console.error("Failed to fetch roles", err)
      }
    }
    fetchMcps()
    fetchRoles()
  }, [])

  const location = useLocation()
  const { uuid } = useParams()

  const isCreateRoute = location.pathname.includes("/create") || location.pathname.includes("/edit/")
  const [currentPage, setCurrentPage] = useState(isCreateRoute ? "create" : "hub")
  const [editingMcp, setEditingMcp] = useState(null)

  // Form states
  const [mcpName, setMcpName] = useState("")
  const [mcpEndpoint, setMcpEndpoint] = useState("")
  const [isPublic, setIsPublic] = useState(false)
  const [headersJson, setHeadersJson] = useState("{\n  \"Content-Type\": \"application/json\"\n}")
  const [envVars, setEnvVars] = useState([])
  const [allowedRoles, setAllowedRoles] = useState([])

  // Dialog / Secret states
  const [showEnvPanel, setShowEnvPanel] = useState(false)
  const [newEnvKey, setNewEnvKey] = useState("")
  const [newEnvValue, setNewEnvValue] = useState("")
  const [envError, setEnvError] = useState("")

  // Search & Pagination states
  const [searchQuery, setSearchQuery] = useState("")
  const [hubPage, setHubPage] = useState(1)
  const itemsPerPage = 6

  const filteredMcps = mcps.filter(item =>
    item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    item.endpoint.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const totalPages = Math.ceil(filteredMcps.length / itemsPerPage) || 1
  const activePage = Math.min(hubPage, totalPages)
  const paginatedMcps = filteredMcps.slice((activePage - 1) * itemsPerPage, activePage * itemsPerPage)

  // Load editing MCP if uuid is present
  useEffect(() => {
    if (uuid && mcps.length > 0) {
      const item = mcps.find(m => m.id === uuid)
      if (item) {
        setEditingMcp(item)
        setMcpName(item.name)
        setMcpEndpoint(item.endpoint)
        setIsPublic(item.is_public)
        setHeadersJson(item.headers || "{\n  \"Content-Type\": \"application/json\"\n}")
        setEnvVars(item.envVars || [])
        setAllowedRoles(item.allowed_roles || [])
        setCurrentPage("create")
      }
    } else if (location.pathname === "/mcp/create") {
      handleCreateClick(false)
    } else if (location.pathname === "/mcp") {
      setCurrentPage("hub")
    }
  }, [uuid, mcps, location.pathname])

  const handleEditClick = (item) => {
    navigate(`/mcp/edit/${item.id}`)
  }

  const handleCreateClick = (doNavigate = true) => {
    if (doNavigate) {
      navigate("/mcp/create")
      return
    }
    setEditingMcp(null)
    setMcpName("")
    setMcpEndpoint("")
    setIsPublic(false)
    setHeadersJson("{\n  \"Content-Type\": \"application/json\"\n}")
    setEnvVars([])
    setAllowedRoles([])
    setCurrentPage("create")
  }

  const handleCancel = () => {
    navigate("/mcp")
  }

  const handleRemoveMcp = async (id) => {
    if (confirm("Are you sure you want to delete this MCP?")) {
      try {
        const res = await fetch(`${API_BASE_URL}/api/mcps/${id}`, {
          method: "DELETE",
          credentials: "include"
        })
        if (res.ok) {
          setMcps(prev => prev.filter(m => m.id !== id))
        }
      } catch (err) {
        console.error("Delete failed", err)
      }
    }
  }

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

  const handleSave = async (e) => {
    e.preventDefault()
    if (!mcpName.trim() || !mcpEndpoint.trim()) return

    const payload = {
      name: mcpName.trim(),
      endpoint: mcpEndpoint.trim(),
      is_public: isPublic,
      headers: headersJson,
      envVars,
      allowed_roles: allowedRoles,
    }

    try {
      const url = editingMcp 
        ? `${API_BASE_URL}/api/mcps/${editingMcp.id}`
        : `${API_BASE_URL}/api/mcps`
      
      const res = await fetch(url, {
        method: editingMcp ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        credentials: "include"
      })

      if (res.ok) {
        const savedMcp = await res.json()
        setMcps(prev => {
          const exists = prev.find(m => m.id === savedMcp.id)
          if (exists) return prev.map(m => m.id === savedMcp.id ? savedMcp : m)
          return [...prev, savedMcp]
        })
        setCurrentPage("hub")
      } else {
        const err = await res.json()
        console.error("Save failed:", err)
      }
    } catch (err) {
      console.error("Save failed", err)
    }
  }

  if (currentPage === "hub") {
    return (
      <div className="space-y-6 w-full text-left">
        <PageHeader
          icon={<Server className="h-4 w-4" />}
          title="MCP Settings"
          description="Configure your Model Context Protocol (MCP) servers in card format."
          actions={
            <>
              <div className="relative w-56">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Search MCPs..."
                  value={searchQuery}
                  onChange={e => {
                    setSearchQuery(e.target.value)
                    setHubPage(1)
                  }}
                  className="pl-9 h-9 text-xs"
                />
              </div>
              {canCreateMcp && (
                <Button size="sm" onClick={handleCreateClick} className="h-9 text-xs cursor-pointer">
                  <Plus className="h-4 w-4 mr-1.5" /> Create MCP
                </Button>
              )}
            </>
          }
        />

        <div className="space-y-6">
          {filteredMcps.length === 0 ? (
            <EmptyState
              icon={<Server />}
              title={searchQuery ? "No servers found" : "No servers configured"}
              description={searchQuery ? "No MCP servers match your search query." : "You have not registered any custom MCP server configurations yet."}
              action={!searchQuery && canCreateMcp ? { label: "Create MCP", onClick: handleCreateClick } : undefined}
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {paginatedMcps.map(item => (
                <EntityCard
                  key={item.id}
                  icon={<Server className="h-4 w-4" />}
                  title={item.name || "Untitled Server"}
                  description={item.endpoint || "No endpoint provided."}
                  badges={[
                    { label: item.is_public ? "Public" : "Private", variant: "outline" }
                  ]}
                  footer={
                    <div className="flex items-center justify-between w-full">
                      <span className="flex items-center gap-1.5 text-muted-foreground">
                        <KeyRound className="h-3 w-3" /> {item.secrets?.length || 0} Secrets
                      </span>
                    </div>
                  }
                  onTest={() => navigate(`/mcps/test/${item.id}`)}
                  onEdit={canEditMcp ? () => handleEditClick(item) : undefined}
                  onDelete={canDeleteMcp ? () => handleRemoveMcp(item.id) : undefined}
                />
              ))}
            </div>
          )}

          {filteredMcps.length > itemsPerPage && (
            <Pagination
              currentPage={activePage}
              totalPages={totalPages}
              onPageChange={setHubPage}
              totalItems={filteredMcps.length}
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
        icon={editingMcp ? <Pencil className="h-[18px] w-[18px]" /> : <PlusCircle className="h-[18px] w-[18px]" />}
        title={editingMcp ? `Edit MCP: ${editingMcp.name}` : "Create MCP"}
        description={editingMcp ? "Modify connection details, endpoint properties, and authorized headers." : "Register a new customized MCP server connection."}
        actions={
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCurrentPage("hub")}
            className="text-xs text-muted-foreground cursor-pointer"
          >
            <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
            Back to MCP List
          </Button>
        }
      />

      <form onSubmit={handleSave} className="space-y-5">
        {/* Card 1: MCP Details */}
        <Card className="p-5 space-y-4">
          <div className="space-y-2">
            <h2 className="text-xs font-semibold text-foreground">MCP Name</h2>
            <Input
              value={mcpName}
              onChange={e => setMcpName(e.target.value)}
              placeholder="e.g. My Custom MCP Service"
              className="text-sm"
              required
            />
          </div>
          <div className="space-y-2">
            <h2 className="text-xs font-semibold text-foreground">MCP Endpoint</h2>
            <Input
              value={mcpEndpoint}
              onChange={e => setMcpEndpoint(e.target.value)}
              placeholder="e.g. http://localhost:3000/mcp"
              className="text-sm"
              required
            />
          </div>
          <div className="flex items-center gap-4 border-t border-border/50 pt-4">
            <span className="flex items-center gap-1.5 text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
              Visibility
              <div className="relative group flex items-center">
                <Info className="h-3.5 w-3.5 text-muted-foreground/60 cursor-help hover:text-foreground transition-colors" />
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2.5 bg-popover text-popover-foreground text-[11px] leading-relaxed rounded-md shadow-lg border border-border/50 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50 text-center font-normal normal-case">
                  <strong>Private</strong> servers are only visible to you. <br/><strong>Public</strong> servers can be used by anyone in the workspace.
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
          <div className="space-y-2 pt-4 border-t border-border/50">
            <h2 className="text-xs font-semibold text-foreground">Allowed Roles
              <span className="ml-1 text-[10px] font-normal text-muted-foreground">(who can access this MCP)</span>
            </h2>
            <CheckboxMultiSelect
              options={roleOptions}
              selected={allowedRoles}
              onChange={setAllowedRoles}
              emptyText="No roles available."
              placeholder="Select roles (Empty = only you)..."
            />
          </div>
        </Card>

        {/* Card 2: Authorization Header Editor */}
        <Card className="p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xs font-semibold text-foreground">Authorization & Headers</h2>
              <p className="text-[10px] text-muted-foreground mt-0.5">
                Input headers in JSON notation. Use the <span className="font-mono text-primary">{"{{SECRET_NAME}}"}</span> token payload format to insert API key overrides.
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setShowEnvPanel(true)}
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
              height="200px"
              language="json"
              theme="vs-dark"
              value={headersJson}
              onChange={val => setHeadersJson(val || "")}
              options={{
                fontSize: 13,
                fontFamily: "'Geist Mono', 'Fira Code', monospace",
                minimap: { enabled: false },
                lineNumbers: "on",
                scrollBeyondLastLine: false,
                wordWrap: "on",
                tabSize: 2,
                automaticLayout: true,
                padding: { top: 14, bottom: 14 },
                scrollbar: { verticalScrollbarSize: 6 },
                renderLineHighlight: "gutter",
                smoothScrolling: true,
              }}
            />
          </div>
        </Card>

        {/* Action Buttons */}
        <div className="flex justify-end gap-2 pb-6">
          <Button type="button" variant="outline" onClick={handleCancel} className="text-xs h-9 cursor-pointer">
            Cancel
          </Button>
          <Button type="submit" className="text-xs h-9 cursor-pointer px-5">
            {editingMcp ? "Save Changes" : "Create MCP"}
          </Button>
        </div>
      </form>

      {/* Secrets Dialog */}
      <Dialog open={showEnvPanel} onOpenChange={setShowEnvPanel}>
        <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-sm">
              <ShieldCheck className="h-4 w-4 text-primary" />
              Environment Variables
            </DialogTitle>
            <DialogDescription className="text-xs">
              Add secrets like API keys. Reference them in your headers block as <span className="font-mono text-primary">{"{{KEY_NAME}}"}</span>. Values are hidden once configured.
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
    </div>
  )
}
