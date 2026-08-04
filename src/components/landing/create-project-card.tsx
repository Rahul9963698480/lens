import { Plus } from 'lucide-react'

import { cn } from '@/lib/utils'

type CreateProjectCardProps = {
  onClick: () => void
  className?: string
}

export function CreateProjectCard({ onClick, className }: CreateProjectCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex w-full max-w-[220px] min-h-28 flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border bg-background px-4 py-6 text-center transition-colors hover:border-brand-navy/40 hover:bg-muted/30 active:bg-muted/40 sm:min-h-32',
        className,
      )}
    >
      <Plus
        className="size-5 text-muted-foreground"
        strokeWidth={1.5}
      />
      <span className="text-xs font-medium text-foreground sm:text-sm">
        Create Project
      </span>
    </button>
  )
}
