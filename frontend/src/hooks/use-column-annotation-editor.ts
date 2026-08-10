import { useCallback, useMemo, useState } from 'react'

import { useUpdateColumnAnnotations } from '@/hooks/use-projects'
import { notify } from '@/lib/notify'
import {
  columnAnnotationFromSchema,
  columnAnnotationToPayload,
  EMPTY_COLUMN_ANNOTATION,
  type ColumnAnnotation,
} from '@/types/annotation'
import type { TableSchema } from '@/types/project'

export function useColumnAnnotationEditor(
  projectId: string | undefined,
  schemaTable: TableSchema | undefined,
) {
  const [annotateColumn, setAnnotateColumn] = useState<string | null>(null)
  const updateColumnAnnotations = useUpdateColumnAnnotations(projectId)

  const selectedAnnotation = useMemo(() => {
    if (!annotateColumn || !schemaTable) return EMPTY_COLUMN_ANNOTATION

    const column = schemaTable.columns.find((item) => item.name === annotateColumn)
    return column ? columnAnnotationFromSchema(column) : EMPTY_COLUMN_ANNOTATION
  }, [annotateColumn, schemaTable])

  const handleSaveAnnotation = useCallback(
    async (columnName: string, annotation: ColumnAnnotation) => {
      if (!projectId || !schemaTable) return

      await updateColumnAnnotations.mutateAsync({
        projectId,
        tableName: schemaTable.table_name,
        columnName,
        payload: columnAnnotationToPayload(annotation),
      })
      notify.success('Annotation saved')
    },
    [projectId, schemaTable, updateColumnAnnotations],
  )

  const openAnnotate = useCallback((columnName: string) => {
    setAnnotateColumn(columnName)
  }, [])

  const closeAnnotate = useCallback(() => {
    setAnnotateColumn(null)
  }, [])

  return {
    openAnnotate,
    annotateSheetProps: {
      open: annotateColumn != null,
      onOpenChange: (open: boolean) => {
        if (!open) closeAnnotate()
      },
      columnName: annotateColumn,
      annotation: selectedAnnotation,
      onSave: handleSaveAnnotation,
      isSaving: updateColumnAnnotations.isPending,
    },
  }
}
