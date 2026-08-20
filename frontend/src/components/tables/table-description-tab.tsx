import { useCallback, useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useUpdateTableAnnotations } from '@/hooks/use-projects'
import { notify } from '@/lib/notify'
import type { TableSchema } from '@/types/project'

type TableDescriptionTabProps = {
  projectId: string | undefined
  schemaTable: TableSchema | undefined
}

export function TableDescriptionTab({
  projectId,
  schemaTable,
}: TableDescriptionTabProps) {
  const savedDescription = schemaTable?.table_description ?? ''
  const [description, setDescription] = useState(savedDescription)
  const updateTableAnnotations = useUpdateTableAnnotations(projectId)

  useEffect(() => {
    setDescription(savedDescription)
  }, [schemaTable?.table_name, savedDescription])

  const handleSave = useCallback(async () => {
    if (!projectId || !schemaTable) return

    await updateTableAnnotations.mutateAsync({
      projectId,
      tableName: schemaTable.table_name,
      payload: { table_description: description.trim() || null },
    })
    notify.success('Table description saved')
  }, [description, projectId, schemaTable, updateTableAnnotations])

  if (!schemaTable) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No table description available.
      </p>
    )
  }

  const isUnchanged = description === savedDescription

  return (
    <div className="flex max-w-2xl flex-col gap-3">
      <div className="flex flex-col gap-2">
        <Label htmlFor="table-description">Table description</Label>
        <Textarea
          id="table-description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="Describe what this table contains…"
          rows={6}
        />
      </div>
      <div>
        <Button
          type="button"
          onClick={handleSave}
          disabled={!projectId || isUnchanged || updateTableAnnotations.isPending}
        >
          {updateTableAnnotations.isPending ? 'Saving…' : 'Save'}
        </Button>
      </div>
    </div>
  )
}
