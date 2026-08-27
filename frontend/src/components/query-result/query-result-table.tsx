import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatQueryValue } from '@/lib/query-result/format-value'
import type { QueryResultData } from '@/lib/query-result/types'
import { cn } from '@/lib/utils'

type QueryResultTableProps = {
  data: QueryResultData
  className?: string
}

export function QueryResultTable({ data, className }: QueryResultTableProps) {
  const { columns, rows } = data
  const rowCount = data.row_count ?? rows.length

  if (columns.length === 0 && rows.length === 0) {
    return (
      <p className="px-3 py-4 text-sm text-muted-foreground">
        Query ran successfully. {rowCount} {rowCount === 1 ? 'row' : 'rows'} returned.
      </p>
    )
  }

  return (
    <div className={cn('overflow-hidden rounded-lg border bg-background', className)}>
      <div className="max-h-80 overflow-auto">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              {columns.map((column) => (
                <TableHead
                  key={column}
                  className="sticky top-0 z-10 h-auto bg-background px-3 py-2 text-xs shadow-[inset_0_-1px_0_0_var(--border)]"
                >
                  {column}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={Math.max(columns.length, 1)}
                  className="py-6 text-center text-muted-foreground"
                >
                  No rows returned.
                </TableCell>
              </TableRow>
            ) : (
              rows.map((row, rowIndex) => (
                <TableRow key={rowIndex}>
                  {columns.map((column) => (
                    <TableCell key={column} className="max-w-56 truncate px-3 py-2 text-sm">
                      {formatQueryValue(row[column])}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
      <p className="border-t px-3 py-2 text-xs text-muted-foreground">
        {rowCount} {rowCount === 1 ? 'row' : 'rows'}
      </p>
    </div>
  )
}
