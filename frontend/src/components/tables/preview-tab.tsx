import { KeyRound } from 'lucide-react'

import { BrandLoader } from '@/components/ui/brand-loader'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  formatCellValue,
  formatColumnType,
  getColumnType,
} from '@/lib/table-column-utils'
import type { TablePreview, TableSchema } from '@/types/project'

type PreviewTabProps = {
  previewTable: TablePreview | undefined
  schemaTable: TableSchema | undefined
  isPreviewLoading?: boolean
  previewError?: boolean
}

export function PreviewTab({
  previewTable,
  schemaTable,
  isPreviewLoading,
  previewError,
}: PreviewTabProps) {
  if (isPreviewLoading) {
    return (
      <BrandLoader
        message="Loading preview…"
        fullHeight={false}
        size={40}
        containerClassName="py-12"
      />
    )
  }

  if (previewError) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Failed to load preview data for this table.
      </p>
    )
  }

  const columns = previewTable?.columns ?? []
  const rows = previewTable?.rows ?? []
  const rowCount = rows.length
  const columnMeta = new Map(
    schemaTable?.columns.map((column) => [column.name, column]) ?? [],
  )

  if (columns.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No columns available for this table.
      </p>
    )
  }

  return (
    <div className="overflow-hidden rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="h-auto w-10 px-3 py-2.5" />
            {columns.map((column) => {
              const meta = columnMeta.get(column)
              const isPrimaryKey = meta?.primary_key === true

              return (
                <TableHead
                  key={column}
                  className="h-auto min-w-[120px] px-4 py-2.5 font-normal"
                >
                  <div className="flex items-center gap-1.5">
                    {isPrimaryKey && (
                      <KeyRound className="size-3 shrink-0 text-amber-500" strokeWidth={2.25} />
                    )}
                    <span className="text-[11px] font-semibold tracking-wide text-foreground uppercase">
                      {column}
                      <span className="ml-1.5 font-normal text-foreground/55">
                        {meta ? formatColumnType(getColumnType(meta)) : 'UNKNOWN'}
                      </span>
                    </span>
                  </div>
                </TableHead>
              )
            })}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length === 0 ? (
            <TableRow>
              <TableCell
                colSpan={columns.length + 1}
                className="py-8 text-center text-muted-foreground"
              >
                No preview rows available.
              </TableCell>
            </TableRow>
          ) : (
            rows.map((row, rowIndex) => (
              <TableRow key={rowIndex}>
                <TableCell className="px-3 py-2 text-xs text-muted-foreground/70 tabular-nums">
                  {rowIndex + 1}
                </TableCell>
                {columns.map((column) => (
                  <TableCell key={column} className="px-4 py-2 text-sm">
                    {formatCellValue(row[column])}
                  </TableCell>
                ))}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
      {rowCount > 0 && <p className="sr-only">{rowCount} rows displayed</p>}
    </div>
  )
}
