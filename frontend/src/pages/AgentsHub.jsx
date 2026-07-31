import React, { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Search, Plus, Cpu, Wrench, Server, ShieldCheck, ShieldOff, Trash2, Bot } from "lucide-react"
import { Pagination } from "@/components/Pagination"
import { PageHeader } from "@/components/PageHeader"
import { EmptyState } from "@/components/EmptyState"
import { EntityCard } from "@/components/EntityCard"
import { usePermissions } from "@/hooks/usePermissions"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"

export function AgentsHub({ agents = [], onCreateAgentClick, onEditAgentClick, onRemoveAgent, onDeployAgent }) {
  const { canCreateAgent, canEditAgent, canDeleteAgent, canExecuteAgent } = usePermissions()
  const [searchQuery, setSearchQuery] = useState("")
  const [currentPage, setCurrentPage] = useState(1)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const itemsPerPage = 6

  const filteredAgents = agents.filter(agent =>
    (agent.name || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
    (agent.description || "").toLowerCase().includes(searchQuery.toLowerCase())
  )

  const totalPages = Math.ceil(filteredAgents.length / itemsPerPage) || 1
  const activePage = Math.min(currentPage, totalPages)
  const paginatedAgents = filteredAgents.slice((activePage - 1) * itemsPerPage, activePage * itemsPerPage)

  const handleConfirmDelete = () => {
    if (deleteTarget) {
      onRemoveAgent?.(deleteTarget.id)
      setDeleteTarget(null)
    }
  }

  return (
    <div className="space-y-6 w-full text-left">
      <PageHeader
        icon={<Cpu className="h-4 w-4" />}
        title="Agent Profile"
        description="Create, manage, and deploy your AI agents with custom configurations."
        actions={
          <>
            <div className="relative w-56">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Search agents..."
                value={searchQuery}
                onChange={e => {
                  setSearchQuery(e.target.value)
                  setCurrentPage(1)
                }}
                className="pl-9 h-9 text-xs"
              />
            </div>
            {canCreateAgent && (
              <Button size="sm" onClick={onCreateAgentClick} className="h-9 text-xs cursor-pointer">
                <Plus className="h-4 w-4 mr-1.5" /> Create Agent
              </Button>
            )}
          </>
        }
      />

      <div className="space-y-6">
        {filteredAgents.length === 0 ? (
          <EmptyState
            icon={<Cpu />}
            title={searchQuery ? "No agents found" : "No agents yet"}
            description={
              searchQuery
                ? `No agents match "${searchQuery}". Try a different keyword.`
                : "You haven't created any agents yet. Build your first AI agent."
            }
            action={
              !searchQuery && canCreateAgent
                ? { label: "Create Agent", onClick: onCreateAgentClick }
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
            {paginatedAgents.map(agent => {
              const guardrailEnabled = agent.guardrailEnabled
              return (
                <EntityCard
                  key={agent.id}
                  icon={<Bot className="h-4.5 w-4.5" />}
                  title={agent.name || "Unnamed Agent"}
                  description={agent.description || "No description provided."}
                  badges={[
                    { label: agent.llm || "—", icon: <Cpu className="h-3 w-3" />, variant: "secondary" },
                    { label: `${agent.toolsCount || 0} tool${(agent.toolsCount || 0) !== 1 ? "s" : ""}`, icon: <Wrench className="h-3 w-3" /> },
                    { label: `${agent.mcpCount || 0} MCP`, icon: <Server className="h-3 w-3" /> },
                    { label: agent.is_public ? "Public" : "Private", variant: "outline" }
                  ]}
                  footer={
                    guardrailEnabled ? (
                      <div className="flex items-center gap-1.5 text-emerald-500">
                        <ShieldCheck className="h-3.5 w-3.5" />
                        <span className="text-[10px] font-semibold uppercase tracking-wide">Guardrails Enabled</span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1.5 text-muted-foreground/60">
                        <ShieldOff className="h-3.5 w-3.5" />
                        <span className="text-[10px] font-medium uppercase tracking-wide">Guardrails Off</span>
                      </div>
                    )
                  }
                  onEdit={canEditAgent ? () => onEditAgentClick?.(agent) : undefined}
                  onDelete={canDeleteAgent ? () => setDeleteTarget(agent) : undefined}
                  onDeploy={canExecuteAgent ? () => onDeployAgent?.(agent) : undefined}
                />
              )
            })}
          </div>
        )}

        {filteredAgents.length > itemsPerPage && (
          <Pagination
            currentPage={activePage}
            totalPages={totalPages}
            onPageChange={setCurrentPage}
            totalItems={filteredAgents.length}
            itemsPerPage={itemsPerPage}
          />
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={open => { if (!open) setDeleteTarget(null) }}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle className="text-sm font-semibold">Delete Agent</DialogTitle>
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
              <Trash2 className="h-3.5 w-3.5" /> Delete Agent
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
