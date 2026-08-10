import { ArrowLeft, Database } from 'lucide-react'

import { useEffect, useMemo, useState } from 'react'

import { Link, useParams } from 'react-router-dom'



import { TableDetailView } from '@/components/tables/table-detail-view'

import { TableExplorer } from '@/components/tables/table-explorer'

import { BrandLoader } from '@/components/ui/brand-loader'

import {

  useProjectPreview,

  useProjects,

  useProjectSchema,

} from '@/hooks/use-projects'



export function TablesPage() {

  const { projectId } = useParams<{ projectId: string }>()

  const [selectedTable, setSelectedTable] = useState<string | null>(null)



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

              <p className="truncate text-xs capitalize text-muted-foreground">

                {schemaQuery.data?.db_name ?? project?.engine ?? 'database'}

              </p>

            </div>

          </div>

        </div>



        <nav className="hidden items-center gap-1 sm:flex">

          <span className="rounded-md bg-muted px-3 py-1.5 text-sm font-medium text-foreground">

            Workspace

          </span>

        </nav>

      </header>



      {isSchemaLoading ? (

        <BrandLoader

          message="Loading schema…"

          containerClassName="flex-1"

        />

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

      )}

    </div>

  )

}


