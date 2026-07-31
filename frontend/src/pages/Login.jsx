import React, { useState } from "react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ShieldCheck, Mail, Lock, UserPlus, LogIn, AlertCircle } from "lucide-react"
import { API_BASE_URL } from "@/config"

export function Login({ onLoginSuccess }) {
  const [isRegister, setIsRegister] = useState(false)
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState("")

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError("")
    setMessage("")
    setLoading(true)

    const endpoint = isRegister ? "/api/auth/signup" : "/api/auth/login"
    
    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
        // Include credentials so that cookies are set correctly on client storage
        credentials: "include", 
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || "Authentication request failed.")
      }

      if (isRegister) {
        setMessage(data.message || "Registration successful! Please log in now.")
        setIsRegister(false)
        setPassword("")
      } else {
        onLoginSuccess()
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4 font-sans select-none text-foreground">
      <Card className="w-full max-w-md bg-card border-border text-left shadow-2xl p-4">
        <CardHeader className="text-center pb-6">
          <div className="flex justify-center mb-4">
            <div className="h-12 w-12 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
              <ShieldCheck className="h-6 w-6" />
            </div>
          </div>
          <CardTitle className="text-xl font-bold tracking-tight text-card-foreground">
            {isRegister ? "Create Enterprise Account" : "Access Workspace Portal"}
          </CardTitle>
          <CardDescription className="text-xs text-muted-foreground mt-1">
            {isRegister ? "Sign up to configure and deploy autonomous agentic loops." : "Sign in using credentials to manage active workspaces."}
          </CardDescription>
        </CardHeader>
        
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs flex items-start gap-2">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            {message && (
              <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-lg text-xs">
                {message}
              </div>
            )}

            <div className="space-y-2">
              <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Email Address</label>
              <div className="relative">
                <Mail className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@company.com"
                  required
                  className="pl-10 border-input focus-visible:ring-1 focus-visible:ring-primary text-foreground placeholder-muted-foreground rounded-lg text-xs h-9"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="pl-10 border-input focus-visible:ring-1 focus-visible:ring-primary text-foreground placeholder-muted-foreground rounded-lg text-xs h-9"
                />
              </div>
            </div>

            <Button 
              type="submit" 
              disabled={loading} 
              className="w-full text-xs font-semibold py-2.5 rounded-lg bg-primary text-primary-foreground hover:bg-primary/95 transition-colors"
            >
              {loading ? (
                "Processing..."
              ) : isRegister ? (
                <span className="flex items-center justify-center gap-1.5 font-bold">
                  <UserPlus className="h-4 w-4" /> Create Account
                </span>
              ) : (
                <span className="flex items-center justify-center gap-1.5 font-bold">
                  <LogIn className="h-4 w-4" /> Log In
                </span>
              )}
            </Button>
          </form>

          <div className="mt-6 text-center border-t border-border pt-4">
            <button
              onClick={() => {
                setIsRegister(!isRegister)
                setError("")
                setMessage("")
              }}
              className="text-xs text-muted-foreground hover:text-foreground underline font-semibold transition-colors cursor-pointer"
            >
              {isRegister ? "Already registered? Sign in" : "Create new workspace account"}
            </button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
