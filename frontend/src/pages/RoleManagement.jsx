import React, { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { API_BASE_URL } from "@/config"
import { PageHeader } from "@/components/PageHeader"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ShieldCheck, Plus, Trash2, ArrowLeft, KeyRound, ListTree } from "lucide-react"
import { toast } from "sonner"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"

const ALL_PERMISSIONS = [
  "tools:read", "tools:create", "tools:edit", "tools:delete", "tools:execute",
  "agents:read", "agents:create", "agents:edit", "agents:delete", "agents:execute",
  "llms:read", "llms:create", "llms:edit", "llms:delete",
  "mcps:read", "mcps:create", "mcps:edit", "mcps:delete", "mcps:execute",
  "guardrails:read", "guardrails:create", "guardrails:edit", "guardrails:delete", "guardrails:execute",
  "roles:manage"
]

export function RoleManagement() {
  const navigate = useNavigate()
  const [roles, setRoles] = useState([])
  const [loading, setLoading] = useState(true)

  const [isModalOpen, setIsModalOpen] = useState(false)
  const [newRoleName, setNewRoleName] = useState("")
  const [selectedPermissions, setSelectedPermissions] = useState([])

  const fetchRoles = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE_URL}/api/roles`, { credentials: "include" })
      if (res.ok) {
        const data = await res.json()
        setRoles(data.items || [])
      }
    } catch (err) {
      toast.error("Failed to fetch roles")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchRoles()
  }, [])

  const handleCreateRole = async () => {
    if (!newRoleName.trim()) {
      toast.error("Role name is required")
      return
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/roles`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          name: newRoleName.trim().toUpperCase(),
          permissions: selectedPermissions
        })
      })
      if (res.ok) {
        toast.success("Role created successfully")
        setIsModalOpen(false)
        setNewRoleName("")
        setSelectedPermissions([])
        fetchRoles()
      } else {
        const data = await res.json()
        toast.error(data.detail || "Failed to create role")
      }
    } catch (err) {
      toast.error("Error creating role")
    }
  }

  const handleDeleteRole = async (roleId) => {
    if (!window.confirm("Are you sure you want to delete this role? Users with this role might lose access.")) return;
    
    try {
      const res = await fetch(`${API_BASE_URL}/api/roles/${roleId}`, {
        method: "DELETE",
        credentials: "include"
      })
      if (res.ok) {
        toast.success("Role deleted successfully")
        fetchRoles()
      } else {
        const data = await res.json()
        toast.error(data.detail || "Failed to delete role")
      }
    } catch (err) {
      toast.error("Error deleting role")
    }
  }

  const togglePermission = (perm) => {
    setSelectedPermissions(prev => 
      prev.includes(perm) ? prev.filter(p => p !== perm) : [...prev, perm]
    )
  }

  return (
    <div className="space-y-6 font-sans">
      <PageHeader 
        icon={<ShieldCheck className="h-[18px] w-[18px]" />}
        title="Custom Roles Management" 
        description="Create and manage dynamic IAM roles and their associated permissions."
        actions={
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/approvals")}
            className="text-xs text-muted-foreground cursor-pointer"
          >
            <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
            Back to Approvals
          </Button>
        }
      />

      <div className="flex justify-end max-w-5xl">
        <Button onClick={() => setIsModalOpen(true)} className="h-9 text-xs font-medium cursor-pointer">
          <Plus className="h-4 w-4 mr-2" />
          Create Custom Role
        </Button>
      </div>

      <div className="max-w-5xl">
        <Card className="bg-card text-left overflow-hidden">
          <CardHeader className="border-b bg-muted/40 pb-5">
            <CardTitle className="text-sm font-bold flex items-center gap-2 uppercase tracking-widest">
              <ListTree className="h-4 w-4 text-primary" /> IAM Roles Directory
            </CardTitle>
            <CardDescription className="text-xs mt-1.5 font-medium max-w-2xl">
              Manage system and custom roles. Custom roles allow you to granularly define API boundaries for different members in the platform.
            </CardDescription>
          </CardHeader>

          <CardContent className="p-0">
            {loading ? (
              <div className="text-xs text-muted-foreground py-16 text-center animate-pulse flex flex-col items-center gap-3">
                <div className="h-6 w-6 rounded-full border-2 border-primary border-t-transparent animate-spin"></div>
                Loading roles...
              </div>
            ) : roles.length === 0 ? (
              <div className="text-xs text-muted-foreground py-16 text-center border-t border-border/50">
                <div className="bg-muted inline-flex p-4 rounded-full mb-3">
                  <ShieldCheck className="h-6 w-6 text-muted-foreground" />
                </div>
                <p>No roles found.</p>
              </div>
            ) : (
              <div className="divide-y">
                {roles.map(role => (
                  <div 
                    key={role.id} 
                    className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 transition-colors hover:bg-muted/50 group"
                  >
                    <div className="flex-1 md:max-w-[200px]">
                      <div className="text-sm font-bold tracking-tight flex items-center gap-2">
                        {role.name}
                      </div>
                      {["ADMIN", "DEVELOPER", "VIEWER"].includes(role.name) && (
                        <div className="mt-2">
                          <Badge variant="secondary" className="text-[10px] font-bold uppercase tracking-widest bg-primary/10 text-primary">
                            System Default
                          </Badge>
                        </div>
                      )}
                    </div>
                    
                    <div className="flex-1 flex flex-wrap gap-1.5">
                      {role.permissions.map((perm, idx) => (
                        <Badge key={idx} variant="outline" className="text-[10px] font-medium bg-background text-muted-foreground">
                          {perm}
                        </Badge>
                      ))}
                      {role.permissions.length === 0 && (
                        <span className="text-xs text-muted-foreground italic flex items-center gap-1.5">
                          <KeyRound className="h-3 w-3" /> No permissions configured
                        </span>
                      )}
                    </div>
                    
                    <div className="flex items-center gap-3">
                      {!["ADMIN", "DEVELOPER", "VIEWER"].includes(role.name) && (
                        <Button 
                          variant="ghost" 
                          size="sm"
                          className="h-8 text-xs font-medium text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={() => handleDeleteRole(role.id)}
                        >
                          <Trash2 className="h-3.5 w-3.5 mr-1.5" /> Delete
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Create Custom Role</DialogTitle>
            <DialogDescription>
              Define a new IAM role and assign specific permissions.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-6 py-4">
            <div className="space-y-2">
              <Label className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Role Name</Label>
              <Input 
                placeholder="e.g. TESTER" 
                value={newRoleName} 
                onChange={(e) => setNewRoleName(e.target.value.toUpperCase())}
                className="font-mono text-sm uppercase"
              />
            </div>
            <div className="space-y-3">
              <Label className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Permissions</Label>
              <div className="grid grid-cols-2 gap-3 p-4 rounded-lg bg-muted/30 border border-border/50">
                {ALL_PERMISSIONS.map(perm => (
                  <div key={perm} className="flex items-center space-x-2">
                    <Checkbox 
                      id={`perm-${perm}`}
                      checked={selectedPermissions.includes(perm)}
                      onCheckedChange={() => togglePermission(perm)}
                    />
                    <label 
                      htmlFor={`perm-${perm}`}
                      className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                    >
                      {perm}
                    </label>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsModalOpen(false)}>Cancel</Button>
            <Button onClick={handleCreateRole}>Create Role</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
