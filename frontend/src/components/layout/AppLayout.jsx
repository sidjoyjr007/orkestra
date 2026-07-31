import { Navbar } from "@/components/layout/Navbar"
import { Sidebar } from "@/components/layout/Sidebar"

export function AppLayout({ children, currentPage, onNavigate, onLogout, currentUser }) {
  const handleNavigate = (path) => {
    onNavigate(path)
  }

  return (
    <div className="relative flex min-h-screen flex-col bg-background text-foreground">
      <Navbar currentPage={currentPage} onNavigate={handleNavigate} onLogout={onLogout} currentUser={currentUser} />
      <div className="flex flex-1 w-full">
        <Sidebar currentPage={currentPage} onNavigate={handleNavigate} />
        <main className="flex-1 min-w-0 flex flex-col p-4 md:p-8">
          {children}
        </main>
      </div>
    </div>
  )
}
