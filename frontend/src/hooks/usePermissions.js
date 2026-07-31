import { useContext } from "react"
import { AuthContext } from "@/App"

export function usePermissions() {
  const user = useContext(AuthContext)
  const permissions = user?.permissions || []
  
  const hasPermission = (permission) => {
    if (permissions.includes("*")) return true
    return permissions.includes(permission)
  }

  return {
    canCreateTool: hasPermission("tools:create"),
    canEditTool: hasPermission("tools:edit"),
    canDeleteTool: hasPermission("tools:delete"),
    canExecuteTool: hasPermission("tools:execute"),
    canCreateAgent: hasPermission("agents:create"),
    canEditAgent: hasPermission("agents:edit"),
    canDeleteAgent: hasPermission("agents:delete"),
    canExecuteAgent: hasPermission("agents:execute"),
    canCreateLlm: hasPermission("llms:create"),
    canEditLlm: hasPermission("llms:edit"),
    canDeleteLlm: hasPermission("llms:delete"),
    canReadLlm: hasPermission("llms:read"),
    canCreateMcp: hasPermission("mcps:create"),
    canEditMcp: hasPermission("mcps:edit"),
    canDeleteMcp: hasPermission("mcps:delete"),
    canCreateGuardrail: hasPermission("guardrails:create"),
    canEditGuardrail: hasPermission("guardrails:edit"),
    canDeleteGuardrail: hasPermission("guardrails:delete"),
    hasPermission
  }
}
