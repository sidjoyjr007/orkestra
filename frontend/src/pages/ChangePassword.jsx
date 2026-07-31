import React, { useState } from "react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PageHeader } from "@/components/PageHeader"
import { KeyRound, Lock, AlertCircle, CheckCircle2 } from "lucide-react"
import { API_BASE_URL } from "@/config"

export function ChangePassword() {
  const [oldPassword, setOldPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [error, setError] = useState("")
  const [success, setSuccess] = useState("")
  const [loading, setLoading] = useState(false)

  const handleUpdatePassword = async (e) => {
    e.preventDefault()
    setError("")
    setSuccess("")

    if (newPassword !== confirmPassword) {
      setError("New passwords do not match.")
      return
    }

    if (newPassword.length < 6) {
      setError("Password must be at least 6 characters long.")
      return
    }

    setLoading(true)
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/change-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
        credentials: "include"
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || "Failed to update password.")
      }

      setSuccess("Your account password has been changed successfully.")
      setOldPassword("")
      setNewPassword("")
      setConfirmPassword("")
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6 font-sans">
      <PageHeader 
        title="Security Settings" 
        description="Manage your account access passwords and credentials."
      />

      <div className="max-w-xl">
        <Card className="bg-card border-border text-left">
          <CardHeader className="border-b border-border pb-4">
            <CardTitle className="text-sm font-semibold text-card-foreground flex items-center gap-2">
              <KeyRound className="h-4 w-4 text-primary" /> Update Password
            </CardTitle>
            <CardDescription className="text-xs text-muted-foreground mt-1">
              Ensure your account uses a secure password to prevent unauthorized deployment access.
            </CardDescription>
          </CardHeader>
          
          <CardContent className="pt-6">
            <form onSubmit={handleUpdatePassword} className="space-y-4">
              {error && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs flex items-start gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              {success && (
                <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-lg text-xs flex items-start gap-2">
                  <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{success}</span>
                </div>
              )}

              <div className="space-y-2">
                <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Current Password</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    type="password"
                    value={oldPassword}
                    onChange={(e) => setOldPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    className="pl-10 border-input focus-visible:ring-1 focus-visible:ring-primary text-foreground placeholder-muted-foreground rounded-lg text-xs h-9"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">New Password</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    className="pl-10 border-input focus-visible:ring-1 focus-visible:ring-primary text-foreground placeholder-muted-foreground rounded-lg text-xs h-9"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Confirm New Password</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="••••••••"
                    required
                    className="pl-10 border-input focus-visible:ring-1 focus-visible:ring-primary text-foreground placeholder-muted-foreground rounded-lg text-xs h-9"
                  />
                </div>
              </div>

              <Button type="submit" disabled={loading} className="text-xs font-semibold px-4 py-2 bg-primary text-primary-foreground hover:bg-primary/90 transition-colors cursor-pointer">
                {loading ? "Updating..." : "Save Password"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
