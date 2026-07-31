import React, { useState } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { ArrowLeft, PlusCircle, Pencil, Check, Search, Info } from "lucide-react"
import { PageHeader } from "@/components/PageHeader"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { API_BASE_URL } from "@/config"

import { useEffect } from "react"

import { Badge } from "@/components/ui/badge"
import { CheckboxMultiSelect } from "@/components/CheckboxMultiSelect"



// ── Main component ────────────────────────────────────────────
export function CreateAgent({
  onSave,
  onBack,
  initialData = null,
}) {
  const isEdit = !!initialData

  const [agentName, setAgentName] = useState(initialData?.name || "")
  const [agentDesc, setAgentDesc] = useState(initialData?.description || "")
  const [systemPrompt, setSystemPrompt] = useState(initialData?.system_prompt || "You are a helpful assistant.")
  const [maxIterations, setMaxIterations] = useState(initialData?.max_iterations || 20)
  const [compactionTokens, setCompactionTokens] = useState(initialData?.compaction_tokens || 30000)
  const [selectedLlm, setSelectedLlm] = useState(initialData?.llm || "gemini-2.5-flash")
  const [selectedTools, setSelectedTools] = useState(initialData?.selectedTools || [])
  const [selectedMcps, setSelectedMcps] = useState(initialData?.selectedMcps || [])
  const [selectedGuardrails, setSelectedGuardrails] = useState(initialData?.selectedGuardrails || [])
  const [allowedRoles, setAllowedRoles] = useState(initialData?.allowed_roles || [])
  const [llmOptions, setLlmOptions] = useState([])
  const [toolOptions, setToolOptions] = useState([])
  const [mcpOptions, setMcpOptions] = useState([])
  const [guardrailOptions, setGuardrailOptions] = useState([])
  const [roleOptions, setRoleOptions] = useState([])
  const [isPublic, setIsPublic] = useState(initialData?.is_public || false)

  useEffect(() => {
    const fetchLlms = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/llms`, { credentials: "include" })
        if (res.ok) {
          const data = await res.json()
          setLlmOptions(data.map(l => ({
            value: l.name,
            label: l.name,
            provider: l.provider,
            model_name: l.model_name
          })))
        }
      } catch (err) {
        console.error("Failed to fetch LLMs", err)
      }
    }
    const fetchTools = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/tools?limit=1000`, { credentials: "include" })
        if (res.ok) {
          const data = await res.json()
          // `/api/tools` returns { items: [...], total: ... }
          setToolOptions(data.items.map(t => ({
            id: t.id,
            label: t.name,
          })))
        }
      } catch (err) {
        console.error("Failed to fetch Tools", err)
      }
    }
    const fetchGuardrails = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/guardrails?limit=1000`, { credentials: "include" })
        if (res.ok) {
          const data = await res.json()
          setGuardrailOptions(data.items.map(g => ({
            id: g.id,
            label: g.name,
            description: g.description
          })))
        }
      } catch (err) {
        console.error("Failed to fetch Guardrails", err)
      }
    }
    const fetchMcps = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/mcps?limit=1000`, { credentials: "include" })
        if (res.ok) {
          const data = await res.json()
          setMcpOptions(data.map(m => ({
            id: m.id,
            label: m.name,
            description: m.endpoint
          })))
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
          setRoleOptions((data.items || []).map(r => ({
            id: r.name,
            label: r.name
          })))
        }
      } catch (err) {
        console.error("Failed to fetch roles", err)
      }
    }
    fetchLlms()
    fetchTools()
    fetchGuardrails()
    fetchMcps()
    fetchRoles()
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!agentName.trim()) return

    const llmOption = llmOptions.find(l => l.value === selectedLlm)
    const payload = {
      ...(initialData?.id && { id: initialData.id }),
      name: agentName.trim(),
      description: agentDesc.trim(),
      system_prompt: systemPrompt.trim(),
      llm: selectedLlm,
      llmProvider: llmOption?.provider || "gemini",
      selectedTools,
      selectedMcps,
      selectedGuardrails,
      max_iterations: parseInt(maxIterations) || 20,
      compaction_tokens: parseInt(compactionTokens) || 30000,
      allowed_roles: allowedRoles,
      is_public: isPublic
    }

    try {
      const res = await fetch(`${API_BASE_URL}/api/agents${isEdit ? `/${initialData.id}` : ""}`, {
        method: isEdit ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        credentials: "include"
      })
      
      const resData = await res.json()
      
      if (!res.ok) {
        throw new Error(resData.detail || "Failed to save agent")
      }
      
      onSave({ ...payload, id: resData.id || payload.id })
      onBack()
    } catch (err) {
      console.error(err)
      // Usually would show toast here, but for now we'll just log
    }
  }

  return (
    <div className="space-y-6 w-full text-left">
      <PageHeader
        icon={isEdit ? <Pencil className="h-[18px] w-[18px]" /> : <PlusCircle className="h-[18px] w-[18px]" />}
        title={isEdit ? `Edit Agent: ${initialData.name}` : "Create Agent"}
        description={isEdit ? "Update this agent's configuration." : "Configure a new AI agent with tools."}
        actions={
          <Button
            variant="ghost"
            size="sm"
            onClick={onBack}
            className="text-xs text-muted-foreground cursor-pointer"
          >
            <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
            Back to Agents
          </Button>
        }
      />

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Card 1: Agent Name + Description */}
        <Card className="p-5 space-y-4">
          <div className="space-y-2">
            <h2 className="text-xs font-semibold text-foreground">Agent Name</h2>
            <Input
              value={agentName}
              onChange={e => setAgentName(e.target.value)}
              placeholder="e.g. Customer Support Bot"
              className="text-sm"
              required
            />
          </div>
          <div className="space-y-2">
            <h2 className="text-xs font-semibold text-foreground">Agent Description
              <span className="ml-1 text-[10px] font-normal text-muted-foreground">(brief summary of what this agent does)</span>
            </h2>
            <Textarea
              value={agentDesc}
              onChange={e => setAgentDesc(e.target.value.slice(0, 300))}
              placeholder="Handles customer queries, resolves tickets, and escalates issues..."
              rows={3}
              maxLength={300}
              className="text-xs resize-none"
            />
            <div className="flex justify-end mt-1">
              <span className={`text-[10px] tabular-nums ${agentDesc.length >= 280 ? agentDesc.length >= 300 ? "text-red-500 font-semibold" : "text-amber-500" : "text-muted-foreground"}`}>
                {agentDesc.length} / 300
              </span>
            </div>
          </div>
          <div className="space-y-2 pt-2 border-t border-border/50">
            <h2 className="text-xs font-semibold text-foreground">System Prompt
              <span className="ml-1 text-[10px] font-normal text-muted-foreground">(the core persona and instructions for the agent)</span>
            </h2>
            <Textarea
              value={systemPrompt}
              onChange={e => setSystemPrompt(e.target.value)}
              placeholder="You are a senior python developer. Write clean and precise code..."
              rows={4}
              className="text-xs resize-none font-mono"
              required
            />
          </div>
          <div className="grid grid-cols-2 gap-4 pt-2 border-t border-border/50">
            <div className="space-y-2">
              <h2 className="text-xs font-semibold text-foreground">Max Iterations
                <span className="ml-1 text-[10px] font-normal text-muted-foreground">(how many turns the agent can take)</span>
              </h2>
              <Input
                type="number"
                min="1"
                max="100"
                value={maxIterations}
                onChange={e => setMaxIterations(e.target.value)}
                className="text-sm"
              />
            </div>
            <div className="space-y-2">
              <h2 className="text-xs font-semibold text-foreground">Compaction Window
                <span className="ml-1 text-[10px] font-normal text-muted-foreground">(token limit before summarizing)</span>
              </h2>
              <Input
                type="number"
                min="1000"
                step="1000"
                value={compactionTokens}
                onChange={e => setCompactionTokens(e.target.value)}
                className="text-sm"
              />
            </div>
          </div>
        </Card>

        {/* Card 2: LLM Selection */}
        <Card className="p-5 space-y-4">
          <h2 className="text-xs font-semibold text-foreground">LLM</h2>
          <Select value={selectedLlm} onValueChange={setSelectedLlm}>
            <SelectTrigger className="w-full text-xs h-9">
              <SelectValue placeholder="Select an LLM">
                {selectedLlm ? llmOptions.find(l => l.value === selectedLlm)?.label : "Select an LLM"}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              {llmOptions.length === 0 && (
                <SelectItem value="none" disabled>No models registered</SelectItem>
              )}
              {llmOptions.map(llm => (
                <SelectItem key={llm.value} value={llm.value} className="text-xs">
                  {llm.label} <span className="text-muted-foreground ml-1">({llm.model_name})</span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Card>

        {/* Card 3: Tool Selection (multiselect) */}
        <Card className="p-5 space-y-4 !overflow-visible">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold text-foreground">Tools
              <span className="ml-1 text-[10px] font-normal text-muted-foreground">({selectedTools.length} selected)</span>
            </h2>
          </div>
          <CheckboxMultiSelect
            options={toolOptions}
            selected={selectedTools}
            onChange={setSelectedTools}
            emptyText="No tools available. Create tools in the Tools Hub first."
          />
        </Card>

        {/* Card 4: Guardrail Selection */}
        <Card className="p-5 space-y-4 !overflow-visible">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold text-foreground">Guardrails
              <span className="ml-1 text-[10px] font-normal text-muted-foreground">({selectedGuardrails.length} selected)</span>
            </h2>
          </div>
          <CheckboxMultiSelect
            options={guardrailOptions}
            selected={selectedGuardrails}
            onChange={setSelectedGuardrails}
            emptyText="No guardrails available. Create them in the Guardrails Hub first."
          />
        </Card>

        {/* Card 5: MCP Selection */}
        <Card className="p-5 space-y-4 !overflow-visible">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold text-foreground">MCP Servers
              <span className="ml-1 text-[10px] font-normal text-muted-foreground">({selectedMcps.length} selected)</span>
            </h2>
          </div>
          <CheckboxMultiSelect
            options={mcpOptions}
            selected={selectedMcps}
            onChange={setSelectedMcps}
            emptyText="No MCP servers available. Add them in the MCP Hub first."
            placeholder="Select MCP servers..."
          />
        </Card>

        {/* Card 6: Allowed Roles Selection */}
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
            placeholder="Select roles that can access this agent (Empty = only you)..."
          />
        </Card>

        {/* Card 7: Visibility Selection */}
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
                  <strong>Private</strong> agents are only visible to you (and roles selected above). <br/><strong>Public</strong> agents can be used by anyone in the workspace.
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
          <Button type="button" variant="outline" onClick={onBack} className="text-xs h-9 cursor-pointer">
            Cancel
          </Button>
          <Button type="submit" className="text-xs h-9 cursor-pointer px-5">
            {isEdit ? "Save Agent" : "Create Agent"}
          </Button>
        </div>
      </form>
    </div>
  )
}
