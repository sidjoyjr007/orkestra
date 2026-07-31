import React from "react"
import { Button } from "@/components/ui/button"

/**
 * EmptyState — Premium zero-data placeholder.
 *
 * Props:
 *   - icon: React element (Lucide icon)
 *   - title: string
 *   - description: string
 *   - action: { label: string, onClick: fn }
 *   - secondaryAction: { label: string, onClick: fn }
 */
export function EmptyState({ icon, title, description, action, secondaryAction }) {
  return (
    <div className="relative flex flex-col items-center justify-center py-20 px-8 text-center overflow-hidden rounded-xl border border-dashed border-border/60">

      {/* Subtle radial gradient backdrop */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 60% 50% at 50% 60%, hsl(var(--primary) / 0.05) 0%, transparent 80%)"
        }}
      />

      {/* Concentric ring icon treatment */}
      <div className="relative mb-7 flex items-center justify-center">
        {/* Outer ring */}
        <div className="absolute w-28 h-28 rounded-full border border-border/30" />
        {/* Mid ring */}
        <div className="absolute w-20 h-20 rounded-full border border-border/50" />
        {/* Inner icon box */}
        <div className="relative z-10 flex items-center justify-center w-12 h-12 rounded-xl bg-muted border border-border text-muted-foreground shadow-sm">
          {icon && React.cloneElement(icon, { className: "h-5 w-5" })}
        </div>
      </div>

      {/* Text */}
      <h3 className="relative text-sm font-semibold text-foreground tracking-tight">
        {title}
      </h3>
      {description && (
        <p className="relative text-xs text-muted-foreground mt-2 max-w-[280px] leading-relaxed">
          {description}
        </p>
      )}

      {/* Action buttons */}
      {(action || secondaryAction) && (
        <div className="relative flex items-center gap-3 mt-7">
          {action && (
            <Button
              size="sm"
              onClick={action.onClick}
              className="text-xs h-8 cursor-pointer px-5"
            >
              {action.label}
            </Button>
          )}
          {secondaryAction && (
            <Button
              variant="ghost"
              size="sm"
              onClick={secondaryAction.onClick}
              className="text-xs h-8 cursor-pointer text-muted-foreground hover:text-foreground"
            >
              {secondaryAction.label}
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
