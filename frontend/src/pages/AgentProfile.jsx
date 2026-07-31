import React from "react"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Cpu } from "lucide-react"
import { PageHeader } from "@/components/PageHeader"

export function AgentProfile({ config = {}, onChange }) {
  return (
    <div className="space-y-6 w-full text-left">
      <PageHeader
        icon={<Cpu className="h-4 w-4" />}
        title="Agent Profile"
        description="Specify core settings, identity codes, and system directives."
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Profile parameters */}
        <div className="md:col-span-2 space-y-4">
          <Card className="p-6 space-y-4">
            <h2 className="text-sm font-semibold text-foreground">Identity Profile</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-xs text-muted-foreground">Agent ID</label>
                <Input 
                  value={config.agent?.id || ""} 
                  onChange={e => onChange({ ...config, agent: { ...config.agent, id: e.target.value } })} 
                  placeholder="e.g. weather-bot"
                  required 
                />
              </div>
              <div className="space-y-2">
                <label className="text-xs text-muted-foreground">Display Name</label>
                <Input 
                  value={config.agent?.name || ""} 
                  onChange={e => onChange({ ...config, agent: { ...config.agent, name: e.target.value } })} 
                  placeholder="e.g. Weather Bot"
                  required 
                />
              </div>
            </div>
          </Card>

          <Card className="p-6 space-y-4">
            <h2 className="text-sm font-semibold text-foreground">System Prompt (Instructions)</h2>
            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Instructions</label>
              <Textarea
                value={config.agent?.system_prompt || ""}
                onChange={e => onChange({ ...config, agent: { ...config.agent, system_prompt: e.target.value } })}
                rows={10}
                placeholder="Instruct the agent on how to behave, what tools it should focus on, and its general persona."
                className="resize-none font-mono text-xs"
                required
              />
            </div>
          </Card>
        </div>

        {/* Documentation Helper */}
        <div className="space-y-4">
          <Card className="p-6 space-y-4 h-full">
            <h2 className="text-sm font-semibold text-foreground">Guidelines</h2>
            <div className="text-xs space-y-4 text-muted-foreground leading-relaxed">
              <div>
                <span className="font-bold text-foreground block mb-1">Clear Directives</span>
                Describe the exact role and task constraints. Specify response formatting rules.
              </div>
              <div>
                <span className="font-bold text-foreground block mb-1">Collaboration</span>
                If you use the Workspace Planner, guide the agent to update and consult the markdown checklists throughout execution loops.
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
