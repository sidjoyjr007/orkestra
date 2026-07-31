import React from "react"
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
  CardAction,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Pencil, Trash2, Play, FlaskConical, Settings2 } from "lucide-react"

/**
 * Reusable entity card using shadcn Card primitives.
 *
 * Props:
 *  - icon        ReactNode   Avatar icon rendered inside a rounded container
 *  - title       string      Primary name / heading (truncated to 1 line)
 *  - description string      Secondary text (clamped to 2 lines)
 *  - badges      Array<{ label, icon?, variant? }>  Stat chips in CardContent
 *  - footer      ReactNode   Anything rendered inside the CardFooter
 *  - onEdit      () => void  Edit callback
 *  - onDelete    () => void  Delete callback
 *  - onDeploy    () => void  Deploy callback (plays simulation session)
 *  - onTest      () => void  Test callback (opens test engine)
 *  - onClick     () => void  Card click (defaults to onEdit)
 */
export function EntityCard({
  icon,
  title = "Untitled",
  description = "No description provided.",
  badges = [],
  footer,
  onEdit,
  onDelete,
  onDeploy,
  onTest,
  onClick,
}) {
  const handleClick = onClick || onEdit

  return (
    <Card
      className="relative group cursor-pointer transition-all duration-200 hover:ring-primary/30 hover:shadow-lg h-full flex flex-col justify-between"
      onClick={handleClick}
    >
      <div className="flex-1 flex flex-col justify-between">
        {/* ── Header: title + description ── */}
        <CardHeader className="flex-none p-4 pb-2">
          <div className="flex items-start gap-3">
            {icon && (
              <div className="h-8 w-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0 border border-primary/20 shadow-sm">
                {icon}
              </div>
            )}
            <div className="min-w-0 flex-1">
              <CardTitle className="truncate text-sm font-semibold tracking-tight mt-1 text-foreground" title={title}>
                {title}
              </CardTitle>
            </div>
          </div>
          <CardDescription className="text-[11px] leading-relaxed line-clamp-2 h-8 mt-3 text-muted-foreground/80 font-medium">
            {description}
          </CardDescription>

          {/* Hover action buttons */}
          {(onEdit || onDelete || onDeploy || onTest) && (
            <div className="absolute top-2.5 right-2.5 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-150 z-10">
               {onTest && (
                <button
                  onClick={e => { e.stopPropagation(); onTest() }}
                  className="flex items-center justify-center h-[26px] w-[26px] rounded-md border border-border bg-background text-muted-foreground hover:border-primary/50 hover:text-primary transition-all cursor-pointer shadow-sm"
                  title="Test Tool"
                >
                  <FlaskConical className="h-3.5 w-3.5" />
                </button>
              )}
              {onDeploy && (
                <button
                  onClick={e => { e.stopPropagation(); onDeploy() }}
                  className="flex items-center justify-center h-[26px] w-[26px] rounded-md border border-border bg-background text-muted-foreground hover:border-primary/50 hover:text-primary transition-all cursor-pointer shadow-xs"
                  title="Manage Agent"
                >
                  <Settings2 className="h-3.5 w-3.5" />
                </button>
              )}
              {onEdit && (
                <button
                  onClick={e => { e.stopPropagation(); onEdit() }}
                  className="flex items-center justify-center h-[26px] w-[26px] rounded-md border border-border bg-background text-muted-foreground hover:border-primary/50 hover:text-primary transition-colors cursor-pointer shadow-xs"
                  title="Edit"
                >
                  <Pencil className="h-3 w-3" />
                </button>
              )}
              {onDelete && (
                <button
                  onClick={e => { e.stopPropagation(); onDelete() }}
                  className="flex items-center justify-center h-[26px] w-[26px] rounded-md border border-border bg-background text-muted-foreground hover:border-red-500/50 hover:text-red-500 transition-colors cursor-pointer shadow-xs"
                  title="Delete"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              )}
            </div>
          )}
        </CardHeader>

        {/* ── Content: badge chips ── */}
        {badges.length > 0 && (
          <CardContent className="flex-1 flex items-end px-4 pt-1 pb-4">
            <div className="flex flex-wrap items-center gap-1.5">
              {badges.map((b, i) => (
                <Badge
                  key={i}
                  variant={b.variant || "outline"}
                  className="text-[9px] gap-1 px-1.5 py-0 font-medium tracking-wide uppercase"
                >
                  {b.icon}
                  {b.label}
                </Badge>
              ))}
            </div>
          </CardContent>
        )}
      </div>

      {/* ── Footer: optional status line ── */}
      {footer && (
        <CardFooter className="flex-none mt-auto px-4 py-3 bg-muted/40 border-t border-border/50 text-[10px] text-muted-foreground font-medium">
          {footer}
        </CardFooter>
      )}
    </Card>
  )
}
