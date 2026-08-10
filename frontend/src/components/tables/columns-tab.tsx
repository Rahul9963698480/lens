import { AnnotateButton } from '@/components/tables/annotate-button'
import { ColumnAnnotateSheet } from '@/components/tables/column-annotate-sheet'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useColumnAnnotationEditor } from '@/hooks/use-column-annotation-editor'
import {
  formatColumnAttribute,
  getColumnDisplayFields,
} from '@/lib/table-column-utils'
import { cn } from '@/lib/utils'
import { hasColumnAnnotation } from '@/types/annotation'
import type { TableSchema } from '@/types/project'

type ColumnsTabProps = {
  projectId: string | undefined
  schemaTable: TableSchema | undefined
}

export function ColumnsTab({ projectId, schemaTable }: ColumnsTabProps) {
  const { openAnnotate, annotateSheetProps } = useColumnAnnotationEditor(
    projectId,
    schemaTable,
  )

  if (!schemaTable) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No column metadata available.
      </p>
    )
  }

  const displayFields = getColumnDisplayFields(schemaTable.columns)

  return (
    <>
      <div className="overflow-hidden rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="px-4">Name</TableHead>
              {displayFields.map((field) => (
                <TableHead key={field.key} className="px-4">
                  {field.label}
                </TableHead>
              ))}
              <TableHead className="px-4 text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {schemaTable.columns.map((column) => (
              <TableRow key={column.name}>
                <TableCell className="px-4 font-medium">
                  <div className="flex items-center gap-2">
                    {column.name}
                    {hasColumnAnnotation(column) && (
                      <span className="rounded bg-brand-teal/10 px-1.5 py-0.5 text-[10px] font-medium text-brand-teal">
                        Annotated
                      </span>
                    )}
                  </div>
                </TableCell>
                {displayFields.map((field) => (
                  <TableCell
                    key={field.key}
                    className={cn(
                      'px-4',
                      field.key === 'type' || field.key === 'foreign_key'
                        ? 'font-mono text-sm'
                        : undefined,
                    )}
                  >
                    {formatColumnAttribute(field.key, field.getValue(column))}
                  </TableCell>
                ))}
                <TableCell className="px-4 text-right">
                  <AnnotateButton onClick={() => openAnnotate(column.name)}>
                    Annotate
                  </AnnotateButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <ColumnAnnotateSheet {...annotateSheetProps} />
    </>
  )
}
