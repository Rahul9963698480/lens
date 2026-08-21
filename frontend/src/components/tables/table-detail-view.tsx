import { ColumnsTab } from '@/components/tables/columns-tab'
import { PreviewTab } from '@/components/tables/preview-tab'
import { RelationshipsTab } from '@/components/tables/relationships-tab'
import { TableDescriptionTab } from '@/components/tables/table-description-tab'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { SchemaRelationship, TablePreview, TableSchema } from '@/types/project'

type TableDetailViewProps = {
  projectId: string | undefined
  schemaTable: TableSchema | undefined
  previewTable: TablePreview | undefined
  relationships: SchemaRelationship[]
  isPreviewLoading?: boolean
  previewError?: boolean
}

export function TableDetailView({
  projectId,
  schemaTable,
  previewTable,
  relationships,
  isPreviewLoading,
  previewError,
}: TableDetailViewProps) {
  const tableName = schemaTable?.table_name ?? previewTable?.table_name ?? 'Table'
  const rowCount = previewTable?.rows?.length ?? 0

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      <div className="shrink-0 border-b px-6 py-3">
        <div className="flex items-center justify-between gap-4">
          <p className="m-0 text-lg font-semibold tracking-tight text-foreground">
            {tableName}
          </p>
          {rowCount > 0 && (
            <span className="shrink-0 text-[11px] text-muted-foreground">
              First {rowCount} rows
            </span>
          )}
        </div>
        {schemaTable?.inferred && (
          <p className="mt-0.5 text-xs text-muted-foreground">
            Schema inferred from sample data.
          </p>
        )}
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden px-6 py-4">
        <Tabs defaultValue="preview" className="flex min-h-0 flex-1 flex-col">
          <TabsList className="mb-4 w-fit shrink-0">
            <TabsTrigger value="table-description">Table Description</TabsTrigger>
            <TabsTrigger value="preview">Preview</TabsTrigger>
            <TabsTrigger value="columns">Columns</TabsTrigger>
            <TabsTrigger value="relationships">Relationships</TabsTrigger>
          </TabsList>

          <TabsContent value="table-description" className="min-h-0 overflow-y-auto">
            <TableDescriptionTab projectId={projectId} schemaTable={schemaTable} />
          </TabsContent>

          <TabsContent value="preview" className="min-h-0 overflow-y-auto">
            <PreviewTab
              previewTable={previewTable}
              schemaTable={schemaTable}
              isPreviewLoading={isPreviewLoading}
              previewError={previewError}
            />
          </TabsContent>

          <TabsContent value="columns" className="min-h-0 overflow-y-auto">
            <ColumnsTab projectId={projectId} schemaTable={schemaTable} />
          </TabsContent>

          <TabsContent value="relationships" className="min-h-0 overflow-y-auto">
            <RelationshipsTab relationships={relationships} tableName={tableName} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
