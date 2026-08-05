import { useCallback, useState } from 'react'
import { Toaster } from 'sonner'

import { AppHeader } from '@/components/landing/app-header'
import { NewProjectDialog } from '@/components/landing/new-project-dialog'
import { ProjectsGrid } from '@/components/landing/projects-grid'

export function LandingPage() {
  const [createDialogOpen, setCreateDialogOpen] = useState(false)

  const handleCreateProject = useCallback(() => {
    setCreateDialogOpen(true)
  }, [])

  return (
    <div className="flex min-h-svh flex-col bg-muted/30">
      <AppHeader onCreateProject={handleCreateProject} />

      <main className="w-full flex-1 px-4 py-5 sm:px-6 sm:py-6 lg:px-10 xl:px-12">
        <div className="mb-4 sm:mb-5">
          <h1 className="m-0 text-xl font-semibold tracking-tight text-foreground sm:text-2xl">
            Your projects
          </h1>
          <p className="mt-1 text-xs text-muted-foreground sm:text-sm">
            Pick up where you left off or create a new project.
          </p>
        </div>

        <ProjectsGrid onCreateProject={handleCreateProject} />
      </main>

      <NewProjectDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
      />

      <Toaster richColors closeButton position="top-center" />
    </div>
  )
}
