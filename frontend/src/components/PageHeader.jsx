import React from "react"

/**
 * PageHeader — Premium full-width page header with gradient banner.
 *
 * Props:
 *   - title: string
 *   - description: string
 *   - icon: React element (Lucide icon)
 *   - actions: React element
 */
export function PageHeader({ title, description, icon, actions }) {
  return (
    <div className="relative mb-8 rounded-xl overflow-hidden">
      {/* Gradient background band */}
      <div
        className="absolute inset-0 opacity-[0.07] pointer-events-none"
        style={{
          background: "radial-gradient(ellipse 80% 120% at 0% 50%, hsl(var(--primary)) 0%, transparent 70%)"
        }}
      />

      {/* Top accent line */}
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-primary/50 via-primary/15 to-transparent" />

      {/* Content */}
      <div className="relative flex flex-col md:flex-row md:items-center justify-between gap-4 px-6 py-5 border border-border/50 rounded-xl bg-background/60 backdrop-blur-sm">
        <div className="flex items-center gap-4">
          {icon && (
            <div className="flex items-center justify-center w-11 h-11 rounded-xl bg-primary/10 border border-primary/25 text-primary shadow-[0_0_16px_-4px_hsl(var(--primary)/0.35)] shrink-0">
              {React.cloneElement(icon, { className: "h-5 w-5" })}
            </div>
          )}

          <div className="min-w-0">
            {/* Bigger, bolder title */}
            <h1 className="text-[17px] font-bold tracking-tight text-foreground leading-tight truncate">
              {title}
            </h1>
            {description && (
              <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed max-w-md line-clamp-2">
                {description}
              </p>
            )}
          </div>
        </div>

        {actions && (
          <div className="flex items-center gap-2 shrink-0 flex-wrap">
            {actions}
          </div>
        )}
      </div>
    </div>
  )
}
