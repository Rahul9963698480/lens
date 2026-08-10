import { AnnotateButton } from '@/components/tables/annotate-button'
import { ColumnAnnotateSheet } from '@/components/tables/column-annotate-sheet'
import { useColumnAnnotationEditor } from '@/hooks/use-column-annotation-editor'
import {
  columnAnnotationFromSchema,
  COLUMN_ANNOTATION_FIELDS,
  hasColumnAnnotation,
} from '@/types/annotation'
import type { TableSchema } from '@/types/project'

type AnnotationsTabProps = {
  projectId: string | undefined
  schemaTable: TableSchema | undefined
}

function AnnotationField({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
        {label}
      </span>
      <p className="m-0 text-sm whitespace-pre-wrap text-foreground">
        {value || '—'}
      </p>
    </div>
  )
}

export function AnnotationsTab({ projectId, schemaTable }: AnnotationsTabProps) {
  const { openAnnotate, annotateSheetProps } = useColumnAnnotationEditor(
    projectId,
    schemaTable,
  )

  if (!schemaTable) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No annotation data available.
      </p>
    )
  }

  const annotatedColumns = schemaTable.columns.filter(hasColumnAnnotation)

  if (annotatedColumns.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No annotations for this table yet. Use the Columns tab to add them.
      </p>
    )
  }

  return (
    <>
      <div className="flex flex-col gap-3">
        {annotatedColumns.map((column) => {
          const annotation = columnAnnotationFromSchema(column)

          return (
            <div key={column.name} className="rounded-lg border p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <span className="rounded-md bg-muted px-2 py-0.5 font-mono text-xs text-muted-foreground">
                  {column.name}
                </span>
                <AnnotateButton onClick={() => openAnnotate(column.name)}>
                  Edit
                </AnnotateButton>
              </div>
              <div className="flex flex-col gap-3">
                {COLUMN_ANNOTATION_FIELDS.map(({ key, label }) => (
                  <AnnotationField
                    key={key}
                    label={label}
                    value={annotation[key]}
                  />
                ))}
              </div>
            </div>
          )
        })}
      </div>

      <ColumnAnnotateSheet {...annotateSheetProps} />
    </>
  )
}
