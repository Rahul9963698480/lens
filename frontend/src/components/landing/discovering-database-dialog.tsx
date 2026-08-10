import { useEffect, useState } from 'react'

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'
import { Circle, CircleCheck } from 'lucide-react'

const DISCOVERY_STEPS = [
  'Schemas',
  'Tables',
  'Columns',
  'Primary Keys',
  'Foreign Keys',
  'Relationships',
] as const

const STEP_INTERVAL_MS = 900

type DiscoveringDatabaseDialogProps = {
  open: boolean
  isComplete: boolean
  onOpenChange?: (open: boolean) => void
}

export function DiscoveringDatabaseDialog({
  open,
  isComplete,
  onOpenChange,
}: DiscoveringDatabaseDialogProps) {
  const [completedCount, setCompletedCount] = useState(0)

  useEffect(() => {
    if (!open) {
      setCompletedCount(0)
      return
    }

    if (isComplete) {
      setCompletedCount(DISCOVERY_STEPS.length)
      return
    }

    const interval = window.setInterval(() => {
      setCompletedCount(
        (prev) => (prev + 1) % (DISCOVERY_STEPS.length + 1),
      )
    }, STEP_INTERVAL_MS)

    return () => window.clearInterval(interval)
  }, [open, isComplete])

  const progressValue = Math.round(
    (completedCount / DISCOVERY_STEPS.length) * 100,
  )

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="gap-6 sm:max-w-md"
        showCloseButton={false}
      >
        <DialogHeader>
          <DialogTitle className="text-lg font-semibold text-brand-navy">
            Discovering database…
          </DialogTitle>
        </DialogHeader>

        <ul className="flex flex-col gap-3">
          {DISCOVERY_STEPS.map((step, index) => {
            const isDone = index < completedCount

            return (
              <li
                key={step}
                className={cn(
                  'flex items-center gap-3 text-sm transition-colors',
                  isDone ? 'text-foreground' : 'text-muted-foreground/70',
                )}
              >
                {isDone ? (
                  <CircleCheck
                    className="size-5 shrink-0 text-brand-teal"
                    strokeWidth={2}
                    aria-hidden
                  />
                ) : (
                  <Circle
                    className="size-5 shrink-0 text-muted-foreground/40"
                    strokeWidth={1.75}
                    aria-hidden
                  />
                )}
                <span className="font-medium">{step}</span>
              </li>
            )
          })}
        </ul>

        <Progress
          value={progressValue}
          className="gap-0 [&_[data-slot=progress-track]]:h-2 [&_[data-slot=progress-track]]:bg-brand-navy/10 [&_[data-slot=progress-indicator]]:rounded-full [&_[data-slot=progress-indicator]]:bg-brand-navy"
        />
      </DialogContent>
    </Dialog>
  )
}
