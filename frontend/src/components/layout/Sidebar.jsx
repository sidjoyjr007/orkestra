import React from "react"
import { Terminal, Cpu, Sparkles, Wrench, Shield, Server, LayoutDashboard, Activity, GitMerge, Layers } from "lucide-react"

export function SidebarContent({ currentPage, onNavigate }) {
  return (
    <div className="space-y-4 py-6 h-full flex flex-col">

      {/* Developer Studio */}
      <div className="px-3 py-2 text-left">
        <h2 className="mb-3 px-4 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Developer Studio</h2>
        <div className="space-y-1">
          <SidebarButton
            icon={Cpu}
            label="Agents"
            active={currentPage === "agents"}
            onClick={() => onNavigate("agents")}
          />
          <SidebarButton
            icon={Sparkles}
            label="LLM Settings"
            active={currentPage === "models"}
            onClick={() => onNavigate("models")}
          />
          <SidebarButton
            icon={Wrench}
            label="Tools Hub"
            active={currentPage === "tools"}
            onClick={() => onNavigate("tools")}
          />
          <SidebarButton
            icon={Server}
            label="MCP Settings"
            active={currentPage === "mcp"}
            onClick={() => onNavigate("mcp")}
          />
          <SidebarButton
            icon={Shield}
            label="Guardrails"
            active={currentPage === "guardrails"}
            onClick={() => onNavigate("guardrails")}
          />
          <SidebarButton
            icon={Activity}
            label="Observability"
            active={currentPage === "observability"}
            onClick={() => onNavigate("observability")}
          />
          <SidebarButton
            icon={Layers}
            label="Swarms"
            active={currentPage === "swarms"}
            onClick={() => onNavigate("swarms")}
          />
        </div>
      </div>
    </div>
  )
}

function SidebarButton({ icon: Icon, label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-4 py-2.5 text-xs font-bold uppercase tracking-wider transition-all border-l-4 cursor-pointer ${active
        ? "bg-primary/10 text-primary border-primary rounded-r-xl font-bold"
        : "text-muted-foreground border-transparent hover:bg-muted hover:text-foreground hover:rounded-xl"
        }`}
    >
      <Icon className="h-4 w-4" />
      {label}
    </button>
  )
}

export function Sidebar({ currentPage, onNavigate }) {
  return (
    <aside className="hidden md:block w-64 shrink-0 border-r sticky top-14 h-[calc(100vh-3.5rem)] overflow-y-auto bg-background/50">
      <SidebarContent currentPage={currentPage} onNavigate={onNavigate} />
    </aside>
  )
}
