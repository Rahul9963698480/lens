import { Database, Plus } from 'lucide-react'

import { Button } from '@/components/ui/button'

type AppHeaderProps = {
  onCreateProject: () => void
}

export function AppHeader({ onCreateProject }: AppHeaderProps) {
  return (
    <header className="sticky top-0 z-10 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="flex w-full items-center justify-between gap-3 px-4 py-3 sm:gap-4 sm:px-6 sm:py-4 lg:px-10 xl:px-12">
        <div className="flex min-w-0 items-center gap-2">
          <Database
            className="size-5 shrink-0 text-brand-navy sm:size-6"
            strokeWidth={2.25}
          />
          <span className="truncate text-base font-semibold tracking-tight text-foreground sm:text-lg">
            Xymphony Lens
          </span>
        </div>

        <Button
          size="sm"
          className="shrink-0 rounded-full px-3 text-white sm:h-8 sm:px-3.5"
          onClick={onCreateProject}
        >
          <Plus data-icon="inline-start" />
          <span className="sm:hidden">Create</span>
          <span className="hidden sm:inline">Create Project</span>
        </Button>
      </div>
    </header>
  )
}
