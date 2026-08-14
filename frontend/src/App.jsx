import React, { useState, useEffect, createContext } from "react"
import { useLocation, useNavigate, Routes, Route, Navigate, useParams } from "react-router-dom"
import { Toaster } from "sonner"
import { AppLayout } from "@/components/layout/AppLayout"
import { AgentsHub } from "@/pages/AgentsHub"
import { CreateAgent } from "@/pages/CreateAgent"
import { ManageAgent } from "@/pages/ManageAgent"
import { LlmSettings } from "@/pages/LlmSettings"
import { McpSettings } from "@/pages/McpSettings"
import { McpTest } from "@/pages/McpTest"
import { ToolsHub } from "@/pages/ToolsHub"
import { CreateTool } from "@/pages/CreateTool"
import { TestTool } from "@/pages/TestTool"
import { TestLlm } from "@/pages/TestLlm"
import { GuardrailsPanel } from "@/pages/GuardrailsPanel"
import { RoleManagement } from "@/pages/RoleManagement"
import { Login } from "@/pages/Login"
import { ChangePassword } from "@/pages/ChangePassword"
import { AdminApprovals } from "@/pages/AdminApprovals"
import { ChatConsole } from "@/pages/ChatConsole"
import { ObservabilityHub } from "@/pages/ObservabilityHub"
import ApiKeys from "@/pages/ApiKeys"
import SwarmsHub from "@/pages/SwarmsHub"
import { ManageSwarm } from "@/pages/ManageSwarm"
import { CreateSwarm } from "@/pages/CreateSwarm"
import { apiClient } from "@/lib/apiClient"

import { useSelector, useDispatch } from "react-redux"
import { removeTool } from "@/store/slices/toolsSlice"
import { fetchCurrentUser, logoutUser } from "@/store/slices/authSlice"
import { fetchAgents, deleteAgent } from "@/store/slices/agentsSlice"
import { createSession } from "@/store/slices/sessionsSlice"

export const AuthContext = createContext(null)

const CreateAgentWrapper = ({ agents, availableTools, onSave, onBack }) => {
  const { uuid } = useParams()
  const agent = uuid ? agents.find(a => a.id === uuid) : null
  return <CreateAgent initialData={agent} availableTools={availableTools} onSave={onSave} onBack={onBack} />
}

const CreateSwarmWrapper = ({ onBack }) => {
  const { uuid } = useParams()
  const [swarm, setSwarm] = useState(null)
  const [loading, setLoading] = useState(!!uuid)

  useEffect(() => {
    if (uuid) {
      apiClient.get('/api/swarms').then(data => {
        const found = data.find(s => s.id === uuid)
        setSwarm(found)
        setLoading(false)
      }).catch(e => {
        console.error("Failed to fetch swarm for edit", e)
        setLoading(false)
      })
    } else {
      setSwarm(null)
      setLoading(false)
    }
  }, [uuid])

  if (loading) return <div className="p-8">Loading swarm data...</div>
  
  // We add a key here to force remount when switching between create (no uuid) and edit (with uuid)
  return <CreateSwarm key={uuid || 'create'} initialData={swarm} onBack={onBack} />
}

export default function App() {
  const dispatch = useDispatch()
  const location = useLocation()
  const navigate = useNavigate()

  // Selectors
  const { currentUser, isAuthenticated, checkingAuth } = useSelector(state => state.auth)
  const agents = useSelector(state => state.agents.items)
  const customTools = useSelector(state => state.tools.items)

  // Verify auth session on load
  useEffect(() => {
    dispatch(fetchCurrentUser())
  }, [dispatch])

  // Fetch agents once authenticated
  useEffect(() => {
    if (isAuthenticated) {
      dispatch(fetchAgents())
    }
  }, [isAuthenticated, dispatch])

  // Derive current page from browser pathname
  const getPageFromPath = (path) => {
    if (path.startsWith("/tools/edit/")) return "create-tool"
    if (path === "/tools/create") return "create-tool"
    if (path.startsWith("/tools")) return "tools"
    if (path.startsWith("/llms/test/")) return "models"
    if (path.startsWith("/models/edit/")) return "models"
    if (path === "/models/create") return "models"
    if (path.startsWith("/mcps/test/")) return "mcp"
    if (path.startsWith("/mcp/edit/")) return "mcp"
    if (path === "/mcp/create") return "mcp"
    if (path.startsWith("/agents/edit/")) return "create-agent"
    if (path.startsWith("/chat/")) return "chat"
    if (path.startsWith("/swarms/edit/")) return "swarms"
    if (path === "/swarms/create") return "swarms"
    if (path.startsWith("/swarms")) return "swarms"
    if (path.startsWith("/observability")) return "observability"
    return path.substring(1) || "profile"
  }

  const currentPage = getPageFromPath(location.pathname)

  const navigateTo = (pageName) => {
    if (pageName.startsWith("/")) {
      navigate(pageName)
    } else {
      navigate(`/${pageName}`)
    }
  }

  const handleLogout = async () => {
    await dispatch(logoutUser())
    navigateTo("profile")
  }

  const handleSaveTool = () => {
    // Relying on central apiClient hooks inside components
  }

  const handleRemoveTool = (toolId) => {
    dispatch(removeTool(toolId))
  }

  const handleCreateSession = (agentId) => {
    const targetAgent = agents.find(a => a.id === agentId)
    if (targetAgent) {
      dispatch(createSession({ agentId, agentName: targetAgent.name }))
    }
    navigateTo(`chat/${agentId}`)
  }

  const handleDeployAgent = (agent) => {
    navigateTo(`manage/${agent.id}`)
  }

  const handleSaveAgent = () => {
    dispatch(fetchAgents())
  }

  const handleRemoveAgent = (agentId) => {
    dispatch(deleteAgent(agentId))
  }

  if (checkingAuth) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background text-foreground font-sans text-xs">
        Checking server authorization...
      </div>
    )
  }

  if (!isAuthenticated) {
    const loginSuccessHandler = () => {
      dispatch(fetchCurrentUser())
    }
    return <Login onLoginSuccess={loginSuccessHandler} />
  }

  return (
    <AuthContext.Provider value={currentUser}>
      <Toaster position="top-right" theme="system" closeButton richColors />
      <AppLayout 
        currentPage={currentPage} 
        onNavigate={navigateTo}
        onLogout={handleLogout}
        currentUser={currentUser}
      >
        <div className="flex-1 min-h-0">
          <Routes>
            <Route path="/profile" element={
              <AgentsHub
                agents={agents}
                onCreateAgentClick={() => navigateTo("create-agent")}
                onEditAgentClick={(agent) => navigateTo(`agents/edit/${agent.id}`)}
                onRemoveAgent={handleRemoveAgent}
                onDeployAgent={handleDeployAgent}
              />
            } />
            <Route path="/create-agent" element={
              <CreateAgentWrapper
                agents={agents}
                availableTools={customTools}
                onSave={handleSaveAgent}
                onBack={() => navigateTo("profile")}
              />
            } />
            <Route path="/agents/edit/:uuid" element={
              <CreateAgentWrapper
                agents={agents}
                availableTools={customTools}
                onSave={handleSaveAgent}
                onBack={() => navigateTo("profile")}
              />
            } />
            <Route path="/manage/:id" element={
              <ManageAgent 
                agents={agents}
                onBack={() => navigateTo("profile")}
              />
            } />
            <Route path="/models" element={
              <LlmSettings />
            } />
            <Route path="/models/create" element={
              <LlmSettings />
            } />
            <Route path="/models/edit/:uuid" element={
              <LlmSettings />
            } />
            <Route path="/tools" element={
              <ToolsHub
                onRemoveTool={handleRemoveTool}
                onCreateToolClick={() => navigateTo("tools/create")}
                onEditToolClick={(tool) => navigateTo(`tools/edit/${tool.id}`)}
              />
            } />
            <Route path="/tools/create" element={
              <CreateTool onSave={handleSaveTool} onBack={() => navigateTo("tools")} />
            } />
            <Route path="/tools/edit/:uuid" element={
              <CreateTool onSave={handleSaveTool} onBack={() => navigateTo("tools")} />
            } />
            <Route path="/tools/test/:uuid" element={
              <TestTool onBack={() => navigateTo("tools")} />
            } />
            <Route path="/llms/test/:uuid" element={
              <TestLlm onBack={() => navigateTo("models")} />
            } />
            <Route path="/mcp" element={<McpSettings />} />
            <Route path="/mcp/create" element={<McpSettings />} />
            <Route path="/mcp/edit/:uuid" element={<McpSettings />} />
            <Route path="/mcps/test/:uuid" element={
              <McpTest onBack={() => navigateTo("mcp")} />
            } />
            <Route path="/guardrails" element={<GuardrailsPanel />} />
            <Route path="/guardrails/create" element={<GuardrailsPanel />} />
            <Route path="/guardrails/edit/:uuid" element={<GuardrailsPanel />} />
            <Route path="/security" element={<ChangePassword />} />
            <Route path="/api-keys" element={<ApiKeys />} />
            <Route path="/approvals" element={<AdminApprovals />} />
            <Route path="/roles" element={<RoleManagement />} />
            <Route path="/swarms" element={<SwarmsHub />} />
            <Route path="/swarms/create" element={<CreateSwarmWrapper onBack={() => navigateTo("swarms")} />} />
            <Route path="/swarms/edit/:uuid" element={<CreateSwarmWrapper onBack={() => navigateTo("swarms")} />} />
            <Route path="/manage-swarm/:id" element={<ManageSwarm />} />
            <Route path="/chat/:uuid" element={<ChatConsole />} />
            <Route path="/observability" element={<ObservabilityHub />} />
            <Route path="*" element={<Navigate to="/profile" replace />} />
          </Routes>
        </div>
      </AppLayout>
    </AuthContext.Provider>
  )
}
