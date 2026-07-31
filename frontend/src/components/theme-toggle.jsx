import React, { useEffect, useState } from "react"
import { Sun, Moon } from "lucide-react"
import { Button } from "@/components/ui/button"

export function ThemeToggle() {
  const [isDark, setIsDark] = useState(false)

  useEffect(() => {
    // Default to light theme
    const root = document.documentElement
    if (!root.classList.contains("dark") && !root.classList.contains("light")) {
      root.classList.add("light")
    }
    setIsDark(root.classList.contains("dark"))
  }, [])

  const toggleTheme = () => {
    const root = document.documentElement
    if (root.classList.contains("dark")) {
      root.classList.remove("dark")
      root.classList.add("light")
      setIsDark(false)
    } else {
      root.classList.remove("light")
      root.classList.add("dark")
      setIsDark(true)
    }
  }

  return (
    <Button variant="ghost" size="icon" onClick={toggleTheme} className="rounded-xl cursor-pointer">
      {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  )
}
