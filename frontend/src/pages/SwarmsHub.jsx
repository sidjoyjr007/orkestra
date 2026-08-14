import React, { useState, useEffect } from 'react'
import { Button } from "@/components/ui/button"
import { Plus, Trash2, Play, RefreshCw, Layers, Bot } from "lucide-react"
import { toast } from "sonner"
import { apiClient } from "@/lib/apiClient"
import { EntityCard } from "@/components/EntityCard"
import { useNavigate } from "react-router-dom"

export default function SwarmsHub() {
  const [swarms, setSwarms] = useState([])
  const [loading, setLoading] = useState(true)
  const [deployingId, setDeployingId] = useState(null)
  
  const navigate = useNavigate()

  useEffect(() => {
    fetchSwarms()
  }, [])

  const fetchSwarms = async () => {
    try {
      const response = await apiClient.get('/api/swarms')
      setSwarms(response || [])
    } catch (error) {
      toast.error("Failed to fetch swarms")
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id) => {
    if (!window.confirm("Are you sure you want to delete this swarm?")) return
    try {
      await apiClient.delete(`/api/swarms/${id}`)
      toast.success("Swarm deleted successfully")
      fetchSwarms()
    } catch (error) {
      toast.error("Failed to delete swarm")
    }
  }

  const handleDeploy = async (id) => {
    setDeployingId(id)
    try {
      await apiClient.post(`/api/deployments/swarm/${id}/deploy`)
      toast.success("Swarm deployed successfully")
      fetchSwarms()
    } catch (error) {
      toast.error("Failed to deploy swarm")
    } finally {
      setDeployingId(null)
    }
  }

  const handleEdit = (swarm) => {
    navigate(`/swarms/edit/${swarm.id}`)
  }

  return (
    <div className="p-8 h-full overflow-y-auto bg-background/50">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight mb-1">Swarm Agents</h1>
          <p className="text-muted-foreground text-sm">Build, orchestrate, and deploy multi-agent swarms.</p>
        </div>
        <Button onClick={() => navigate('/swarms/create')}>
          <Plus className="w-4 h-4 mr-2" />
          Create Swarm
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      ) : swarms.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 border border-dashed rounded-lg bg-card/50">
          <Layers className="w-12 h-12 text-muted-foreground mb-4 opacity-50" />
          <h3 className="text-lg font-medium mb-1">No Swarms Found</h3>
          <p className="text-sm text-muted-foreground mb-4 text-center max-w-sm">
            Create your first Swarm to orchestrate multiple agents working together seamlessly.
          </p>
          <Button onClick={() => navigate('/swarms/create')} variant="outline">
            Create Swarm
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {swarms.map((swarm) => (
            <EntityCard
              key={swarm.id}
              icon={<Layers className="h-4.5 w-4.5" />}
              title={swarm.name || "Unnamed Swarm"}
              description={swarm.description || "No description provided."}
              badges={[
                { label: `${swarm.subagents?.length || 0} Subagent${(swarm.subagents?.length || 0) !== 1 ? "s" : ""}`, icon: <Bot className="h-3 w-3" /> }
              ]}
              onEdit={(e) => { e?.stopPropagation?.(); handleEdit(swarm); }}
              onDelete={(e) => { e?.stopPropagation?.(); handleDelete(swarm.id); }}
              onDeploy={(e) => { e?.stopPropagation?.(); navigate(`/manage-swarm/${swarm.id}`) }}
            />
          ))}
        </div>
      )}
    </div>
  )
}
