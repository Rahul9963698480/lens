import { ArrowLeft, Database } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { PlaygroundChat } from '@/components/playground/playground-chat'
import { TableDetailView } from '@/components/tables/table-detail-view'
import { TableExplorer } from '@/components/tables/table-explorer'
import { BrandLoader } from '@/components/ui/brand-loader'
import {
  useProjectPreview,
  useProjects,
  useProjectSchema,
} from '@/hooks/use-projects'
import { cn } from '@/lib/utils'

type ProjectView = 'workspace' | 'playground'

export function TablesPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const [selectedTable, setSelectedTable] = useState<string | null>(null)
  const [view, setView] = useState<ProjectView>('workspace')

  const { data: projects = [] } = useProjects()
  const project = projects.find((item) => item.id === projectId)

  const schemaQuery = useProjectSchema(projectId)
  const previewQuery = useProjectPreview(projectId)
  const tableNames = useMemo(
    () => schemaQuery.data?.tables.map((table) => table.table_name) ?? [],
    [schemaQuery.data],
  )

  useEffect(() => {
    if (tableNames.length > 0 && !selectedTable) {
      setSelectedTable(tableNames[0])
    }
  }, [tableNames, selectedTable])

  const schemaTable = schemaQuery.data?.tables.find(
    (table) => table.table_name === selectedTable,
  )
  const previewTable = previewQuery.data?.tables.find(
    (table) => table.table_name === selectedTable,
  )
  const tableRelationships = schemaTable?.relationships ?? []
  const isSchemaLoading = schemaQuery.isPending
  const hasSchemaError = schemaQuery.isError

  return (
    <div className="flex h-svh flex-col overflow-hidden bg-background">
      <header className="sticky top-0 z-10 flex w-full items-center justify-between gap-3 border-b bg-background/95 px-4 py-3 backdrop-blur sm:px-6 lg:px-8">
        <div className="flex min-w-0 items-center gap-3">
          <Link
            to="/"
            aria-label="Back to projects"
            className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
          </Link>
          <div className="flex min-w-0 items-center gap-2">
            <Database className="size-5 shrink-0 text-brand-navy" strokeWidth={2.25} />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-foreground">
                {project?.name ?? 'Project'}
              </p>
              <p className="truncate text-xs capitalize text-foreground/80">
                {schemaQuery.data?.db_name ?? project?.engine ?? 'database'}
              </p>
            </div>
          </div>
        </div>

        <nav
          role="tablist"
          aria-label="Project view"
          className="flex items-center rounded-full bg-muted p-1"
        >
          <button
            type="button"
            role="tab"
            aria-selected={view === 'workspace'}
            className={cn(
              'rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors',
              view === 'workspace'
                ? 'bg-primary text-primary-foreground shadow-sm'
                : 'text-foreground/70 hover:bg-background/60 hover:text-foreground',
            )}
            onClick={() => setView('workspace')}
          >
            Workspace
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={view === 'playground'}
            className={cn(
              'rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors',
              view === 'playground'
                ? 'bg-primary text-primary-foreground shadow-sm'
                : 'text-foreground/70 hover:bg-background/60 hover:text-foreground',
            )}
            onClick={() => setView('playground')}
          >
            Playground
          </button>
        </nav>
      </header>

      <div className={cn(view === 'playground' ? 'flex min-h-0 flex-1' : 'hidden')}>
        <PlaygroundChat projectId={projectId} />
      </div>

      {view === 'workspace' &&
        (isSchemaLoading ? (
          <BrandLoader message="Loading schema…" containerClassName="flex-1" />
        ) : hasSchemaError ? (
          <div className="flex flex-1 items-center justify-center p-6">
            <p className="text-sm text-muted-foreground">
              Failed to load project schema.
            </p>
          </div>
        ) : (
          <div className="flex min-h-0 flex-1">
            <TableExplorer
              tables={tableNames}
              selectedTable={selectedTable}
              onSelectTable={setSelectedTable}
            />
            {selectedTable ? (
              <TableDetailView
                projectId={projectId}
                schemaTable={schemaTable}
                previewTable={previewTable}
                relationships={tableRelationships}
                isPreviewLoading={previewQuery.isPending}
                previewError={previewQuery.isError}
              />
            ) : (
              <div className="flex flex-1 items-center justify-center">
                <p className="text-sm text-muted-foreground">Select a table to view.</p>
              </div>
            )}
          </div>
        ))}
    </div>
  )
}
