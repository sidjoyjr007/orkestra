import React, { useEffect, useState } from "react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { PageHeader } from "@/components/PageHeader"
import { ShieldCheck, UserCheck, UserX, AlertCircle, Save, Settings } from "lucide-react"
import { toast } from "sonner"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { API_BASE_URL } from "@/config"
import { useNavigate } from "react-router-dom"

export function AdminApprovals() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [availableRoles, setAvailableRoles] = useState([])
  const [selectedRoles, setSelectedRoles] = useState({})
  const [loadingRoles, setLoadingRoles] = useState(true)
  const navigate = useNavigate()

  const fetchRoles = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/roles`, { credentials: "include" })
      if (res.ok) {
        const data = await res.json()
        setAvailableRoles(data.items || [])
      }
    } catch (err) {
      console.error("Failed to load roles", err)
    } finally {
      setLoadingRoles(false)
    }
  }

  const fetchUsers = async () => {
    setLoading(true)
    setError("")
    try {
      const res = await fetch(`${API_BASE_URL}/api/users`, { credentials: "include" })
      if (!res.ok) throw new Error("Failed to retrieve users.")
      const data = await res.json()
      setUsers(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchUsers()
    fetchRoles()
  }, [])

  const handleApprove = async (userId, role) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/users/${userId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role }),
        credentials: "include"
      })
      if (!res.ok) {
        const d = await res.json()
        throw new Error(d.detail || "Failed to update user.")
      }
      toast.success("User successfully updated.")
      fetchUsers()
      // Clear the local state so the button hides
      setSelectedRoles(prev => {
        const next = { ...prev }
        delete next[userId]
        return next
      })
    } catch (err) {
      toast.error(err.message)
    }
  }

  const handleRevoke = async (userId) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/users/${userId}/revoke`, {
        method: "POST",
        credentials: "include"
      })
      if (!res.ok) {
        const d = await res.json()
        throw new Error(d.detail || "Failed to revoke.")
      }
      toast.success("Access revoked.")
      fetchUsers()
    } catch (err) {
      toast.error(err.message)
    }
  }

  const handleRoleSelection = (userId, role) => {
    setSelectedRoles(prev => ({ ...prev, [userId]: role }));
  }

  return (
    <div className="space-y-6 font-sans">
      <PageHeader 
        title="Admin Settings" 
        description="Admin dashboard to approve, manage access, and assign roles to registered users."
        actions={
          <Button onClick={() => navigate("/roles")} variant="outline" className="h-9 text-xs font-medium cursor-pointer">
            <Settings className="h-4 w-4 mr-2" />
            Manage Custom Roles
          </Button>
        }
      />

      <div className="max-w-5xl">
        <Card className="bg-card text-left overflow-hidden">
          <CardHeader className="border-b bg-muted/40 pb-5">
            <CardTitle className="text-sm font-bold flex items-center gap-2 uppercase tracking-widest">
              <ShieldCheck className="h-4 w-4 text-primary" /> Directory
            </CardTitle>
            <CardDescription className="text-xs mt-1.5 font-medium max-w-2xl">
              Manage all internal sandbox accounts. Active users can access the application based on their roles. Only Administrators can grant or revoke privileges.
            </CardDescription>
          </CardHeader>
          
          <CardContent className="p-0">
            {error && (
              <div className="m-6 p-4 bg-destructive/10 border border-destructive/20 text-destructive rounded-xl text-xs flex items-start gap-2">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                <span className="font-medium leading-relaxed">{error}</span>
              </div>
            )}

            {loading ? (
              <div className="text-xs text-muted-foreground py-16 text-center animate-pulse flex flex-col items-center gap-3">
                <div className="h-6 w-6 rounded-full border-2 border-primary border-t-transparent animate-spin"></div>
                Loading directory...
              </div>
            ) : users.length === 0 ? (
              <div className="text-xs text-muted-foreground py-16 text-center border-t border-border/50">
                <div className="bg-muted inline-flex p-4 rounded-full mb-3">
                  <UserX className="h-6 w-6 text-muted-foreground" />
                </div>
                <p>No users found in the system.</p>
              </div>
            ) : (
              <div className="divide-y">
                {users.map(user => {
                  const currentRole = selectedRoles[user.id] || user.role;
                  const isRoleChanged = currentRole !== user.role;
                  
                  return (
                  <div 
                    key={user.id} 
                    className={`p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 transition-colors hover:bg-muted/50 group ${!user.is_active ? 'bg-muted/20' : ''}`}
                  >
                    <div className="flex-1">
                      <div className="text-sm font-bold tracking-tight flex items-center gap-2">
                        {user.email}
                      </div>
                      <div className="mt-2 flex gap-2">
                        <Badge variant="secondary" className="text-[10px] font-bold uppercase tracking-widest">
                          {user.role}
                        </Badge>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-3">
                      <Select 
                        value={currentRole} 
                        onValueChange={(val) => handleRoleSelection(user.id, val)}
                      >
                        <SelectTrigger className="w-[130px] h-8 text-xs font-medium">
                          <SelectValue placeholder="Select role" />
                        </SelectTrigger>
                        <SelectContent>
                          {availableRoles.map(r => (
                            <SelectItem key={r.id} value={r.name} className="text-xs font-medium">
                              {r.name.charAt(0) + r.name.slice(1).toLowerCase()}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>

                      {!user.is_active ? (
                        <Button 
                          size="sm" 
                          onClick={() => handleApprove(user.id, currentRole)}
                          className="h-8 w-[100px] text-[10px] font-bold uppercase tracking-widest flex items-center gap-1.5"
                        >
                          <UserCheck className="h-3.5 w-3.5" /> Approve
                        </Button>
                      ) : (
                        <div className="flex items-center gap-2">
                          {isRoleChanged && (
                            <Button 
                              size="sm"
                              variant="default" 
                              onClick={() => handleApprove(user.id, currentRole)}
                              className="h-8 w-[100px] text-[10px] font-bold uppercase tracking-widest flex items-center gap-1.5"
                            >
                              <Save className="h-3.5 w-3.5" /> Update
                            </Button>
                          )}
                          <Button 
                            size="sm" 
                            variant="destructive"
                            onClick={() => handleRevoke(user.id)}
                            className="h-8 w-[100px] text-[10px] font-bold uppercase tracking-widest flex items-center gap-1.5"
                          >
                            <UserX className="h-3.5 w-3.5" /> Revoke
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>
                )})}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
