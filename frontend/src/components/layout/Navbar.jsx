import React from "react"
import { Menu, Sparkles, LogOut, User } from "lucide-react"
import { ThemeToggle } from "@/components/theme-toggle"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetTrigger, SheetTitle, SheetHeader } from "@/components/ui/sheet"
import { SidebarContent } from "@/components/layout/Sidebar"

export function Navbar({ currentPage, onNavigate, onLogout, currentUser }) {
  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto flex h-14 max-w-screen-2xl items-center justify-between px-4">
        {/* Mobile menu trigger */}
        <div className="flex md:hidden items-center">
          <Sheet>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="mr-2">
                <Menu className="h-5 w-5" />
                <span className="sr-only">Toggle Menu</span>
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="pr-0">
              <SheetHeader>
                <SheetTitle className="text-left font-bold flex items-center gap-2 mb-4 uppercase text-xs tracking-widest">
                  <Sparkles className="h-4 w-4" /> AgentFoundry
                </SheetTitle>
              </SheetHeader>
              <SidebarContent currentPage={currentPage} onNavigate={onNavigate} /> 
            </SheetContent>
          </Sheet>
          <div className="flex items-center gap-2 font-bold uppercase text-xs tracking-wider text-foreground">
            <Sparkles className="h-4 w-4 text-primary" />
            <span>AgentFoundry</span>
          </div>
        </div>

        {/* Desktop Title */}
        <div className="hidden md:flex items-center gap-2 font-bold uppercase text-xs tracking-wider text-foreground cursor-pointer" onClick={() => onNavigate("profile")}>
          <Sparkles className="h-4 w-4 text-primary" />
          <span>AgentFoundry</span>
        </div>

        <div className="flex items-center space-x-2 relative">
          <ThemeToggle />
          
          {/* User profile dropdown container */}
          <ProfileDropdown 
            currentUser={currentUser} 
            onNavigate={onNavigate} 
            onLogout={onLogout} 
            currentPage={currentPage}
          />
        </div>
      </div>
    </header>
  )
}

function ProfileDropdown({ currentUser, onNavigate, onLogout, currentPage }) {
  const [open, setOpen] = React.useState(false)
  const dropdownRef = React.useRef(null)

  // Close dropdown on click outside
  React.useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  if (!currentUser) return null

  return (
    <div className="relative" ref={dropdownRef}>
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setOpen(!open)}
        className={`h-9 w-9 rounded-lg transition-colors ${
          open || currentPage === "security" || currentPage === "approvals" 
            ? "text-primary bg-primary/10" 
            : "text-muted-foreground hover:text-foreground"
        }`}
        title="User Account"
      >
        <User className="h-4 w-4" />
      </Button>

      {open && (
        <div className="absolute right-0 mt-2 w-56 rounded-xl border border-border bg-card shadow-2xl p-2 z-50 text-left">
          {/* User Header Info */}
          <div className="px-3 py-2 border-b border-border mb-1.5">
            <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Account Email</div>
            <div className="text-xs font-semibold text-foreground truncate mt-0.5">{currentUser.email}</div>
            <div className="inline-block px-1.5 py-0.5 bg-primary/10 text-primary text-[8px] font-bold rounded uppercase tracking-wider mt-1.5">
              {currentUser.role}
            </div>
          </div>

          <div className="space-y-0.5">
            {/* Admin Approvals Link */}
            {currentUser.role === "ADMIN" && (
              <button
                onClick={() => {
                  onNavigate("approvals")
                  setOpen(false)
                }}
                className={`w-full text-left px-3 py-2 text-xs font-semibold rounded-lg hover:bg-muted hover:text-foreground transition-colors flex items-center gap-2 cursor-pointer ${
                  currentPage === "approvals" ? "text-primary bg-primary/5" : "text-foreground"
                }`}
              >
                <Sparkles className="h-3.5 w-3.5" /> User Management
              </button>
            )}

            {/* Change Password settings option */}
            <button
              onClick={() => {
                onNavigate("security")
                setOpen(false)
              }}
              className={`w-full text-left px-3 py-2 text-xs font-semibold rounded-lg hover:bg-muted hover:text-foreground transition-colors flex items-center gap-2 cursor-pointer ${
                currentPage === "security" ? "text-primary bg-primary/5" : "text-foreground"
              }`}
            >
              <User className="h-3.5 w-3.5" /> Change Password
            </button>

            {/* Log Out action option */}
            <button
              onClick={() => {
                onLogout()
                setOpen(false)
              }}
              className="w-full text-left px-3 py-2 text-xs font-semibold text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-lg transition-colors flex items-center gap-2 border-t border-border mt-1.5 pt-2 cursor-pointer"
            >
              <LogOut className="h-3.5 w-3.5" /> Log Out
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
