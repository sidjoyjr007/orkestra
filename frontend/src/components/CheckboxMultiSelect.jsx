import React, { useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Search, X, ChevronDown, Check } from "lucide-react"

export function CheckboxMultiSelect({ options, selected, onChange, emptyText, placeholder = "Select options..." }) {
  const [isOpen, setIsOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")

  const toggleOption = (id) => {
    if (selected.includes(id)) {
      onChange(selected.filter(s => s !== id))
    } else {
      onChange([...selected, id])
    }
  }

  const removeOption = (id, e) => {
    e.stopPropagation()
    onChange(selected.filter(s => s !== id))
  }

  const filteredOptions = options.filter(opt =>
    opt.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (opt.description || "").toLowerCase().includes(searchQuery.toLowerCase())
  )

  const selectedItems = options.filter(opt => selected.includes(opt.id))

  return (
    <div className="space-y-2 relative overflow-visible">
      {/* Selected Items Badges Container */}
      <div 
        onClick={() => setIsOpen(!isOpen)}
        className="flex min-h-[38px] w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-xs shadow-xs cursor-pointer hover:bg-muted/10 transition-colors"
      >
        <div className="flex flex-wrap gap-1.5 flex-1 min-w-0 mr-2">
          {selectedItems.length === 0 ? (
            <span className="text-muted-foreground text-xs">{placeholder}</span>
          ) : (
            selectedItems.map(item => (
              <Badge 
                key={item.id} 
                variant="secondary" 
                className="text-[10px] pl-2 pr-1 py-0.5 gap-1 font-medium bg-secondary text-secondary-foreground rounded flex items-center shrink-0"
              >
                <span>{item.label}</span>
                <span 
                  onClick={(e) => removeOption(item.id, e)} 
                  className="rounded hover:bg-muted/80 p-0.5 text-muted-foreground hover:text-foreground cursor-pointer"
                >
                  <X className="h-2.5 w-2.5" />
                </span>
              </Badge>
            ))
          )}
        </div>
        <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
      </div>

      {/* Options Dropdown Menu */}
      {isOpen && (
        <>
          {/* Invisible Backdrop to close on click outside */}
          <div className="fixed inset-0 z-30" onClick={() => setIsOpen(false)} />
          
          <div className="absolute top-full left-0 z-40 mt-1 w-full rounded-md border border-border bg-popover text-popover-foreground shadow-md p-1 space-y-1.5 min-w-[200px]">
            <div className="relative px-1 pt-1">
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
                  const isChecked = selected.includes(opt.id)
                  return (
                    <div
                      key={opt.id}
                      onClick={() => toggleOption(opt.id)}
                      className={`flex items-center gap-2.5 rounded-md px-2 py-1.5 cursor-pointer text-xs transition-colors ${
                        isChecked 
                          ? "bg-accent text-accent-foreground font-medium" 
                          : "hover:bg-muted text-foreground"
                      }`}
                    >
                      <div
                        className={`flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded border transition-colors ${
                          isChecked
                            ? "bg-primary border-primary text-primary-foreground"
                            : "border-muted-foreground/40"
                        }`}
                      >
                        {isChecked && <Check className="h-2.5 w-2.5" />}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="font-medium leading-none">{opt.label}</p>
                        {opt.description && (
                          <p className="text-[10px] text-muted-foreground leading-normal mt-0.5 line-clamp-1">{opt.description}</p>
                        )}
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
