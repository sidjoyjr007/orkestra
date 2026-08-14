import React, { useState, useEffect } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { ArrowLeft, PlusCircle, Pencil, Check, Trash2, Bot, Layers } from "lucide-react"
import { PageHeader } from "@/components/PageHeader"
import { SearchableSelect } from "@/components/SearchableSelect"
import { API_BASE_URL } from "@/config"
import { apiClient } from "@/lib/apiClient"
import { toast } from "sonner"
import { useSelector } from "react-redux"

export function CreateSwarm({
  onSave,
  onBack,
  initialData = null,
}) {
  const isEdit = !!initialData
  const availableAgents = useSelector(state => state.agents.items)
  const agentOptions = availableAgents.map(a => ({ id: a.id, label: a.name }))

  const [name, setName] = useState(initialData?.name || "")
  const [description, setDescription] = useState(initialData?.description || "")
  const [leaderAgentId, setLeaderAgentId] = useState(initialData?.leader_agent_id || "")
  const [subagents, setSubagents] = useState(
    initialData?.subagents?.length > 0 
      ? initialData.subagents.map(sa => ({ agent_id: sa.agent_id, role_description: sa.role_description || "" }))
      : [{ agent_id: "", role_description: "" }]
  )
  
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!initialData && availableAgents.length > 0 && !leaderAgentId) {
      setLeaderAgentId(availableAgents[0].id)
      if (subagents.length === 1 && !subagents[0].agent_id) {
        setSubagents([{ agent_id: availableAgents[0].id, role_description: "" }])
      }
    }
  }, [availableAgents, initialData, leaderAgentId, subagents])

  const handleAddSubagent = () => {
    setSubagents([...subagents, { agent_id: availableAgents[0]?.id || "", role_description: "" }])
  }

  const handleRemoveSubagent = (index) => {
    const newSubagents = [...subagents]
    newSubagents.splice(index, 1)
    setSubagents(newSubagents)
  }

  const handleSubagentChange = (index, field, value) => {
    const newSubagents = [...subagents]
    newSubagents[index][field] = value
    setSubagents(newSubagents)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim()) return

    setLoading(true)
    const payload = {
      name: name.trim(),
      description: description.trim(),
      leader_agent_id: leaderAgentId,
      subagents: subagents
    }

    try {
      if (isEdit) {
        await apiClient.put(`/api/swarms/${initialData.id}`, payload)
        toast.success("Swarm updated successfully")
      } else {
        await apiClient.post('/api/swarms', payload)
        toast.success("Swarm created successfully")
      }
      if (onSave) onSave()
      if (onBack) onBack()
    } catch (error) {
      toast.error(isEdit ? "Failed to update swarm" : "Failed to create swarm")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6 w-full text-left">
      <PageHeader
        icon={isEdit ? <Pencil className="h-[18px] w-[18px]" /> : <PlusCircle className="h-[18px] w-[18px]" />}
        title={isEdit ? `Edit Swarm: ${initialData.name}` : "Create Swarm"}
        description={isEdit ? "Update this swarm's configuration and subagents." : "Configure a new multi-agent swarm."}
        actions={
          <Button
            variant="ghost"
            size="sm"
            onClick={onBack}
            className="text-xs text-muted-foreground cursor-pointer"
          >
            <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
            Back to Swarms
          </Button>
        }
      />

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Card 1: Swarm Name + Description */}
        <Card className="p-5 space-y-4">
          <div className="space-y-2">
            <h2 className="text-xs font-semibold text-foreground">Swarm Name</h2>
            <Input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. Market Research Swarm"
              className="text-sm"
              required
            />
          </div>

          <div className="space-y-2">
            <h2 className="text-xs font-semibold text-foreground">Description
              <span className="ml-1 text-[10px] font-normal text-muted-foreground">(brief summary of what this swarm orchestrates)</span>
            </h2>
            <Textarea
              value={description}
              onChange={e => setDescription(e.target.value.slice(0, 300))}
              placeholder="Coordinates specialized agents to research markets and draft reports..."
              rows={3}
              maxLength={300}
              className="text-xs resize-none"
            />
            <div className="flex justify-end mt-1">
              <span className={`text-[10px] tabular-nums ${description.length >= 280 ? description.length >= 300 ? "text-red-500 font-semibold" : "text-amber-500" : "text-muted-foreground"}`}>
                {description.length} / 300
              </span>
            </div>
          </div>
        </Card>

        {/* Card 2: Orchestrator */}
        <Card className="p-5 space-y-4 !overflow-visible">
          <div className="space-y-2">
            <h2 className="text-xs font-semibold text-foreground">Leader Agent (Orchestrator)
              <span className="ml-1 text-[10px] font-normal text-muted-foreground">(receives the initial prompt and delegates tasks)</span>
            </h2>
            <SearchableSelect 
              options={agentOptions}
              value={leaderAgentId}
              onChange={setLeaderAgentId}
              placeholder="Select Orchestrator Agent"
            />
          </div>
        </Card>

        {/* Card 3: Subagents */}
        <Card className="p-5 space-y-4 !overflow-visible">
          <div className="flex justify-between items-center pb-2 border-b border-border/50">
            <h2 className="text-xs font-semibold text-foreground">Subagents
              <span className="ml-1 text-[10px] font-normal text-muted-foreground">(specialized agents the leader can delegate to)</span>
            </h2>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleAddSubagent}
              className="h-8 text-xs"
            >
              <PlusCircle className="w-3.5 h-3.5 mr-1" />
              Add Subagent
            </Button>
          </div>
          
          <div className="space-y-4 pt-2">
            {subagents.map((subagent, index) => (
              <div key={index} className="relative rounded-lg border border-border bg-card p-4 space-y-4 shadow-sm">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => handleRemoveSubagent(index)}
                  disabled={subagents.length === 1}
                  className="absolute top-2 right-2 h-8 w-8 text-muted-foreground hover:text-destructive"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>

                <div className="space-y-2 pr-10">
                  <h2 className="text-xs font-semibold text-foreground">Agent</h2>
                  <SearchableSelect 
                    options={agentOptions}
                    value={subagent.agent_id}
                    onChange={(val) => handleSubagentChange(index, 'agent_id', val)}
                    placeholder="Select Subagent"
                  />
                </div>
                
                <div className="space-y-2">
                  <h2 className="text-xs font-semibold text-foreground">Role / Specialization</h2>
                  <Textarea
                    placeholder="e.g. Fetches and analyzes real-time financial data"
                    value={subagent.role_description}
                    onChange={(e) => handleSubagentChange(index, 'role_description', e.target.value)}
                    className="text-xs resize-none"
                    rows={3}
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Submit Actions */}
        <div className="flex justify-end gap-3 pt-4">
          <Button
            type="button"
            variant="outline"
            onClick={onBack}
            className="h-9 px-4 text-sm bg-background border-muted-foreground/20 hover:bg-muted/50"
          >
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={loading || !name.trim()}
            className="h-9 px-6 text-sm bg-primary text-primary-foreground hover:bg-primary/90"
          >
            {loading ? "Saving..." : (isEdit ? "Update Swarm" : "Create Swarm")}
          </Button>
        </div>
      </form>
    </div>
  )
}
