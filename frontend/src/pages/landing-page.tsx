import { useCallback, useState } from 'react'

import { AppHeader } from '@/components/landing/app-header'
import { NewProjectDialog } from '@/components/landing/new-project-dialog'
import { ProjectsGrid } from '@/components/landing/projects-grid'
import { useProjects } from '@/hooks/use-projects'

export function LandingPage() {
  const [createDialogOpen, setCreateDialogOpen] = useState(false)

  const { data: projects = [] } = useProjects()

  const handleCreateProject = useCallback(() => {
    setCreateDialogOpen(true)
  }, [])

  const projectCount = projects.length

  return (
    <div className="flex min-h-svh flex-col bg-linear-to-b from-muted/40 via-background to-background">
      <AppHeader onCreateProject={handleCreateProject} />

      <main className="w-full flex-1 px-4 py-8 sm:px-6 sm:py-10 lg:px-10 xl:px-12">
        <div className="mb-8 sm:mb-10">
          <p className="text-xs font-medium uppercase tracking-wider text-brand-navy/70">
            Workspace
          </p>

          {/* <div className="mt-1 flex items-center justify-between gap-4">
            <h1 className="m-0 lg:text-2xl  font-semibold tracking-tight text-foreground sm:text-3xl">
              Your projects
            </h1>

            {!projectCount ? null : (
              <div className="inline-flex shrink-0 items-center rounded-full border border-border/60 bg-card px-3 py-1.5 text-xs text-muted-foreground shadow-sm">
                <span className="font-medium text-foreground">{projectCount}</span>
                <span className="ml-1">
                  {projectCount === 1 ? 'project' : 'projects'}
                </span>
              </div>
            )}
          </div> */}

          <p className="mt-2 max-w-xl text-sm text-muted-foreground">
            Pick up where you left off or connect a new database to explore
            schemas and data.
          </p>
        </div>

        <ProjectsGrid onCreateProject={handleCreateProject} />
      </main>

      <NewProjectDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
      />
    </div>
  )
}
