import React, { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Wrench, Plus, Trash2, Search, Globe, KeyRound, Box, Server, ShieldAlert } from "lucide-react"
import { Pagination } from "@/components/Pagination"
import { PageHeader } from "@/components/PageHeader"
import { EmptyState } from "@/components/EmptyState"
import { EntityCard } from "@/components/EntityCard"
import { toast } from "sonner"
import { useDispatch, useSelector } from "react-redux"
import { setTools } from "@/store/slices/toolsSlice"
import { API_BASE_URL } from "@/config"
import { usePermissions } from "@/hooks/usePermissions"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog"

export function ToolsHub({ onRemoveTool, onCreateToolClick, onEditToolClick }) {
  const navigate = useNavigate()
  const { canCreateTool, canEditTool, canDeleteTool, canExecuteTool } = usePermissions()
  const [searchQuery, setSearchQuery] = useState("")
  const [debouncedSearch, setDebouncedSearch] = useState("")
  const [currentPage, setCurrentPage] = useState(1)
  const [deleteTarget, setDeleteTarget] = useState(null)
  
  const [totalCount, setTotalCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const itemsPerPage = 6

  const dispatch = useDispatch()
  const tools = useSelector(state => state.tools.items)

  // Setup search debouncing
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(searchQuery)
      setCurrentPage(1)
    }, 400) // 400ms debounce interval
    
    return () => clearTimeout(handler)
  }, [searchQuery])

  // Fetch paginated search results directly from backend database API
  const fetchTools = async () => {
    setLoading(true)
    const offset = (currentPage - 1) * itemsPerPage
    const query = debouncedSearch.trim()
    const url = `${API_BASE_URL}/api/tools?limit=${itemsPerPage}&offset=${offset}${query ? `&q=${encodeURIComponent(query)}` : ""}`
    
    try {
      const res = await fetch(url, { credentials: "include" })
      if (res.ok) {
        const data = await res.json()
        dispatch(setTools(data.items || []))
        setTotalCount(data.total || 0)
      }
    } catch (err) {
      console.error("Error retrieving tools list", err)
    } finally {
      setLoading(false)
    }
  }

  // Fetch search results when currentPage or debouncedSearch criteria shifts
  useEffect(() => {
    fetchTools()
  }, [currentPage, debouncedSearch])

  const totalPages = Math.ceil(totalCount / itemsPerPage) || 1

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return
    try {
      const res = await fetch(`${API_BASE_URL}/api/tools/${deleteTarget.id}`, {
        method: "DELETE",
        credentials: "include"
      })
      if (res.ok) {
        toast.success("Tool deleted successfully!")
        onRemoveTool(deleteTarget.id)
        setDeleteTarget(null)
        // Reset to first page and reload
        setCurrentPage(1)
        fetchTools()
      } else {
        const data = await res.json()
        throw new Error(data.detail || "Failed to delete tool.")
      }
    } catch (err) {
      toast.error(`Error deleting tool: ${err.message}`)
      console.error("Failed to delete tool", err)
    }
  }



  return (
    <div className="space-y-6 w-full text-left">
      <PageHeader
        icon={<Wrench className="h-4 w-4" />}
        title="Tools Hub"
        description="Create, manage, and organize your custom Python tool capabilities."
        actions={
          <>
            <div className="relative w-56">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Search tools..."
                value={searchQuery}
                onChange={e => {
                  setSearchQuery(e.target.value)
                  setCurrentPage(1)
                }}
                className="pl-9 h-9 text-xs"
              />
            </div>
            {canCreateTool && (
              <Button size="sm" onClick={onCreateToolClick} className="h-9 text-xs cursor-pointer">
                <Plus className="h-4 w-4 mr-1.5" /> Create Tool
              </Button>
            )}
          </>
        }
      />

      <div className="space-y-6">
        {loading ? (
          <div className="text-center py-12 text-xs text-muted-foreground">Loading tools catalog...</div>
        ) : tools.length === 0 ? (
          <EmptyState
            icon={<Wrench />}
            title={searchQuery ? "No tools found" : "No tools yet"}
            description={
              searchQuery
                ? `No tools match "${searchQuery}". Try a different keyword.`
                : "You haven't created any tools yet. Build your first custom Python capability."
            }
            action={
              !searchQuery
                ? { label: "Create Tool", onClick: onCreateToolClick }
                : undefined
            }
            secondaryAction={
              searchQuery
                ? { label: "Clear search", onClick: () => { setSearchQuery(""); setCurrentPage(1) } }
                : undefined
            }
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {tools.map(tool => (
              <EntityCard
                key={tool.id}
                icon={<Wrench className="h-4 w-4" />}
                title={tool.name || "Untitled Tool"}
                description={tool.desc?.trim() || "No description provided."}
                badges={[
                  { label: tool.tool_type || "SANDBOX", icon: tool.tool_type === "HOST" ? <Server className="h-3 w-3" /> : <Box className="h-3 w-3" />, variant: tool.tool_type === "HOST" ? "default" : "secondary" },
                  { label: tool.is_public ? "Public" : "Private", variant: "outline" },
                  ...(tool.requires_approval ? [{ label: "Approval Required", icon: <ShieldAlert className="h-3 w-3" />, variant: "destructive" }] : []),
                  ...(tool.status === "DRAFT" ? [{ label: "Draft", variant: "destructive" }] : [])
                ]}
                footer={
                  <div className="flex items-center justify-between w-full text-muted-foreground">
                    <span className="flex items-center gap-1.5"><Globe className="h-3 w-3" /> {tool.dependencies?.length || 0} Dependencies</span>
                    <span className="flex items-center gap-1.5"><KeyRound className="h-3 w-3" /> {tool.envVars?.length || 0} Secrets</span>
                  </div>
                }
                onTest={canExecuteTool ? () => navigate(`/tools/test/${tool.id}`) : undefined}
                onEdit={canEditTool ? () => onEditToolClick && onEditToolClick(tool) : undefined}
                onDelete={canDeleteTool ? () => setDeleteTarget(tool) : undefined}
              />
            ))}
          </div>
        )}

        {!loading && totalCount > itemsPerPage && (
          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            onPageChange={setCurrentPage}
            totalItems={totalCount}
            itemsPerPage={itemsPerPage}
          />
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={open => { if (!open) setDeleteTarget(null) }}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle className="text-sm font-semibold">Delete Tool</DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground mt-1">
              Are you sure you want to remove{" "}
              <span className="font-mono font-bold text-foreground break-all">{deleteTarget?.name}</span>?
              {" "}This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="pt-4 flex gap-2 justify-end">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDeleteTarget(null)}
              className="text-xs cursor-pointer"
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleConfirmDelete}
              className="text-xs cursor-pointer gap-1.5"
            >
              <Trash2 className="h-3.5 w-3.5" /> Delete Tool
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
