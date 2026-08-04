import { CreateProjectCard } from '@/components/landing/create-project-card'

type ProjectsGridProps = {
  onCreateProject: () => void
}

export function ProjectsGrid({ onCreateProject }: ProjectsGridProps) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4 lg:grid-cols-3 lg:gap-5">
      <CreateProjectCard onClick={onCreateProject} />
    </div>
  )
}
