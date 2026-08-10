import { useCallback, useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import type { ColumnAnnotation } from '@/types/annotation'

type ColumnAnnotateSheetProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  columnName: string | null
  annotation: ColumnAnnotation
  onSave: (columnName: string, annotation: ColumnAnnotation) => void | Promise<void>
  isSaving?: boolean
}

export function ColumnAnnotateSheet({
  open,
  onOpenChange,
  columnName,
  annotation,
  onSave,
  isSaving = false,
}: ColumnAnnotateSheetProps) {
  const [form, setForm] = useState<ColumnAnnotation>(annotation)

  useEffect(() => {
    if (open) {
      setForm(annotation)
    }
  }, [open, annotation])

  const updateField = useCallback(
    <K extends keyof ColumnAnnotation>(key: K, value: ColumnAnnotation[K]) => {
      setForm((current) => ({ ...current, [key]: value }))
    },
    [],
  )

  const handleSave = useCallback(async () => {
    if (!columnName) return

    try {
      await onSave(columnName, form)
      onOpenChange(false)
    } catch {
      // Keep the sheet open so the user can retry.
    }
  }, [columnName, form, onOpenChange, onSave])

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full gap-0 overflow-y-auto p-0 sm:max-w-md"
      >
        <SheetHeader className="border-b px-6 py-4">
          <div className="flex items-center gap-2 pr-8">
            <SheetTitle className="text-lg font-semibold">Annotate</SheetTitle>
            {columnName && (
              <span className="rounded-md bg-muted px-2 py-0.5 font-mono text-xs text-muted-foreground">
                {columnName}
              </span>
            )}
          </div>
        </SheetHeader>

        <div className="flex flex-1 flex-col gap-5 px-6 py-5">
          <div className="flex flex-col gap-2">
            <Label htmlFor="column-description">Description</Label>
            <Textarea
              id="column-description"
              value={form.description}
              onChange={(event) => updateField('description', event.target.value)}
              rows={4}
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="business-name">Business name</Label>
            <Input
              id="business-name"
              value={form.businessName}
              onChange={(event) => updateField('businessName', event.target.value)}
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="null-meaning">Null meaning</Label>
            <Input
              id="null-meaning"
              value={form.nullMeaning}
              onChange={(event) => updateField('nullMeaning', event.target.value)}
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="value-mapping">Value mapping</Label>
            <Textarea
              id="value-mapping"
              value={form.valueMapping}
              onChange={(event) => updateField('valueMapping', event.target.value)}
              placeholder="VIP = Premium Customer"
              rows={3}
            />
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="caveats">Caveats</Label>
            <Textarea
              id="caveats"
              value={form.caveats}
              onChange={(event) => updateField('caveats', event.target.value)}
              rows={3}
            />
          </div>
        </div>

        <SheetFooter className="border-t px-6 py-4">
          <Button type="button" onClick={handleSave} disabled={!columnName || isSaving}>
            {isSaving ? 'Saving…' : 'Save'}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
