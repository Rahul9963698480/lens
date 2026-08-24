import { ArrowUpRight, Database, FileSpreadsheet, Leaf, Plus } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { BrandLoader } from '@/components/ui/brand-loader'
import { useProjects } from '@/hooks/use-projects'
import { cn } from '@/lib/utils'
import type { Project } from '@/types/project'

type ProjectsGridProps = {
  onCreateProject: () => void
}

const ENGINE_META = {
  postgres: {
    label: 'PostgreSQL',
    icon: Database,
    badgeClass: 'bg-brand-navy/10 text-brand-navy border-brand-navy/20',
    iconClass: 'bg-brand-teal text-white',
  },
  mongodb: {
    label: 'MongoDB',
    icon: Leaf,
    badgeClass: 'bg-brand-teal/10 text-brand-teal border-brand-teal/20',
    iconClass: 'bg-brand-teal text-white',
  },
  xlsx: {
    label: 'Excel',
    icon: FileSpreadsheet,
    badgeClass: 'bg-emerald-500/10 text-emerald-800 border-emerald-500/20',
    iconClass: 'bg-brand-teal text-white',
  },
} as const

function getEngineMeta(engine: string) {
  const key = engine.toLowerCase() as keyof typeof ENGINE_META
  return ENGINE_META[key] ?? {
    label: engine,
    icon: Database,
    badgeClass: 'bg-muted text-muted-foreground border-border',
    iconClass: 'bg-brand-teal text-white',
  }
}

function formatCreatedAt(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(value))
}

function ProjectCard({ project }: { project: Project }) {
  const navigate = useNavigate()
  const meta = getEngineMeta(project.engine)
  const EngineIcon = meta.icon

  return (
    <button
      type="button"
      onClick={() => navigate(`/table/${project.id}`)}
      className={cn(
        'group relative flex w-full flex-col rounded-xl border border-border/60 bg-card p-5 text-left shadow-sm transition-all',
        'hover:-translate-y-0.5 hover:border-brand-navy/25 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-navy/30',
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div
          className={cn(
            'flex size-10 shrink-0 items-center justify-center rounded-lg',
            meta.iconClass,
          )}
        >
          <EngineIcon className="size-5" strokeWidth={2} />
        </div>
        <Badge
          variant="outline"
          className={cn('rounded-full capitalize', meta.badgeClass)}
        >
          {meta.label}
        </Badge>
      </div>

      <h3 className="mt-4 truncate text-base font-semibold tracking-tight text-foreground">
        {project.name}
      </h3>

      <p className="mt-1 truncate text-sm text-muted-foreground">
        {project.engine.toLowerCase() === 'xlsx' ? (
          project.db_name
        ) : (
          <>
            {project.db_host ?? '—'}
            <span className="text-muted-foreground/60"> / </span>
            {project.db_name}
          </>
        )}
      </p>

      <div className="mt-5 flex items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>Created {formatCreatedAt(project.created_at)}</span>
        <span className="inline-flex items-center gap-1 font-medium text-brand-navy opacity-0 transition-opacity group-hover:opacity-100">
          Open
          <ArrowUpRight className="size-3.5" strokeWidth={2.25} />
        </span>
      </div>
    </button>
  )
}

function CreateProjectCard({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'group flex w-full min-h-[168px] flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border/80 bg-card/50 p-5 text-center shadow-sm transition-all',
        'hover:-translate-y-0.5 hover:border-brand-navy/35 hover:bg-card hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-navy/30',
      )}
    >
      <div className="flex size-11 items-center justify-center rounded-full border border-dashed border-border bg-muted/50 transition-colors group-hover:border-brand-navy/30 group-hover:bg-brand-navy/5">
        <Plus
          className="size-5 text-muted-foreground transition-colors group-hover:text-brand-navy"
          strokeWidth={2}
        />
      </div>
      <div>
        <p className="text-sm font-medium text-foreground">Create project</p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Connect a database or spreadsheet
        </p>
      </div>
    </button>
  )
}

export function ProjectsGrid({ onCreateProject }: ProjectsGridProps) {
  const { data: projects = [], isLoading } = useProjects()

  if (isLoading) {
    return <BrandLoader message="Loading projects…" />
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      <CreateProjectCard onClick={onCreateProject} />
      {projects.map((project) => (
        <ProjectCard key={project.id} project={project} />
      ))}
    </div>
  )
}
