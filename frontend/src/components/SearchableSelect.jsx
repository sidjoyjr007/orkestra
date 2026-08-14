import React, { useState, useRef, useEffect } from "react"
import { Input } from "@/components/ui/input"
import { Search, ChevronDown, Check } from "lucide-react"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"

export function SearchableSelect({ options, value, onChange, emptyText, placeholder = "Select an option..." }) {
  const [isOpen, setIsOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const triggerRef = useRef(null)
  const [triggerWidth, setTriggerWidth] = useState(0)

  useEffect(() => {
    if (isOpen && triggerRef.current) {
      setTriggerWidth(triggerRef.current.offsetWidth)
    }
  }, [isOpen])

  const filteredOptions = options.filter(opt =>
    opt.label.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const selectedItem = options.find(opt => opt.id === value)

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger className="w-full p-0 border-none bg-transparent outline-none">
        <div 
          ref={triggerRef}
          className="flex min-h-[36px] w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm shadow-xs cursor-pointer hover:bg-muted/10 transition-colors"
        >
          <span className="truncate mr-2">
            {selectedItem ? selectedItem.label : <span className="text-muted-foreground">{placeholder}</span>}
          </span>
          <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
        </div>
      </PopoverTrigger>

      <PopoverContent 
        className="p-1 min-w-[200px]" 
        align="start"
        style={{ width: triggerWidth > 0 ? `${triggerWidth}px` : undefined }}
      >
        <div className="relative px-1 pt-1 mb-1">
          <Search className="absolute left-3 top-3 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="pl-8 h-8 text-xs bg-background w-full"
            autoFocus
          />
        </div>
        
        <div className="max-h-48 overflow-y-auto px-1 pb-1 space-y-0.5">
          {filteredOptions.length === 0 ? (
            <p className="text-xs text-muted-foreground italic py-3 text-center">
              {searchQuery ? "No matching options found." : (emptyText || "No options available.")}
            </p>
          ) : (
            filteredOptions.map(opt => {
              const isChecked = value === opt.id
              return (
                <div
                  key={opt.id}
                  onClick={() => {
                    onChange(opt.id)
                    setIsOpen(false)
                    setSearchQuery("")
                  }}
                  className={`flex items-center gap-2 rounded-md px-2 py-1.5 cursor-pointer text-xs transition-colors ${
                    isChecked 
                      ? "bg-accent text-accent-foreground font-medium" 
                      : "hover:bg-muted text-foreground"
                  }`}
                >
                  <div className="flex h-4 w-4 shrink-0 items-center justify-center">
                    {isChecked && <Check className="h-3.5 w-3.5" />}
                  </div>
                  <div className="flex flex-col min-w-0">
                    <span className="truncate">{opt.label}</span>
                  </div>
                </div>
              )
            })
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}
