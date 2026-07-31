import React from "react"
import { Button } from "@/components/ui/button"
import { ChevronLeft, ChevronRight } from "lucide-react"

export function Pagination({ currentPage, totalPages, onPageChange, totalItems, itemsPerPage }) {
  if (totalPages <= 1) return null

  const startItem = (currentPage - 1) * itemsPerPage + 1
  const endItem = Math.min(currentPage * itemsPerPage, totalItems)

  return (
    <div className="flex flex-col items-center justify-center space-y-2 pt-6">
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={currentPage === 1}
          onClick={() => onPageChange(Math.max(currentPage - 1, 1))}
          className="cursor-pointer"
        >
          <ChevronLeft className="h-4 w-4 mr-1" /> Previous
        </Button>

        {Array.from({ length: totalPages }, (_, i) => i + 1).map(pageNum => (
          <Button
            key={pageNum}
            variant={currentPage === pageNum ? "default" : "outline"}
            size="sm"
            onClick={() => onPageChange(pageNum)}
            className="cursor-pointer min-w-8"
          >
            {pageNum}
          </Button>
        ))}

        <Button
          variant="outline"
          size="sm"
          disabled={currentPage === totalPages}
          onClick={() => onPageChange(Math.min(currentPage + 1, totalPages))}
          className="cursor-pointer"
        >
          Next <ChevronRight className="h-4 w-4 ml-1" />
        </Button>
      </div>
      {totalItems !== undefined && itemsPerPage !== undefined && (
        <span className="text-[10px] text-muted-foreground">
          Showing {startItem} to {endItem} of {totalItems} items
        </span>
      )}
    </div>
  )
}
