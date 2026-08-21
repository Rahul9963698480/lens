import { Check, Pencil, Play, X } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { formatCellValue } from '@/lib/table-column-utils'
import { cn } from '@/lib/utils'
import type { SqlExecuteResponse } from '@/types/sql'

type SqlFeedback = 'correct' | 'incorrect' | null

type SqlQueryCardProps = {
  sql: string
  executing?: boolean
  result?: SqlExecuteResponse
  executeError?: string
  onSqlChange: (sql: string) => void
  onExecute: () => void
  onFeedback?: (feedback: 'correct' | 'incorrect') => void
}

export function SqlQueryCard({
  sql,
  executing,
  result,
  executeError,
  onSqlChange,
  onExecute,
  onFeedback,
}: SqlQueryCardProps) {
  const [feedback, setFeedback] = useState<SqlFeedback>(null)
  const [isEditing, setIsEditing] = useState(false)
  const canExecute = sql.trim().length > 0 && !executing

  const handleFeedback = (value: 'correct' | 'incorrect') => {
    setFeedback(value)
    onFeedback?.(value)
  }

  return (
    <div className="w-full min-w-0 rounded-xl border border-border/80 bg-muted/40 p-3">
      <div className="mb-2 flex items-center justify-between gap-3">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          SQL query
        </p>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            className={cn(
              'border-blue-200 text-blue-700 hover:bg-blue-50 hover:text-blue-800',
              isEditing && 'border-blue-500 bg-blue-50',
            )}
            onClick={() => setIsEditing(!isEditing)}
          >
            <Pencil className="size-3.5" />
            Edit
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            aria-pressed={feedback === 'correct'}
            className={cn(
              'border-emerald-200 text-emerald-700 hover:bg-emerald-50 hover:text-emerald-800',
              feedback === 'correct' && 'border-emerald-500 bg-emerald-50',
            )}
            onClick={() => handleFeedback('correct')}
          >
            <Check className="size-3.5" />
            Correct
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            aria-pressed={feedback === 'incorrect'}
            className={cn(
              'border-red-200 text-red-700 hover:bg-red-50 hover:text-red-800',
              feedback === 'incorrect' && 'border-red-500 bg-red-50',
            )}
            onClick={() => handleFeedback('incorrect')}
          >
            <X className="size-3.5" />
            Incorrect
          </Button>
          <Button
            type="button"
            size="sm"
            disabled={!canExecute}
            className="bg-brand-teal text-white hover:bg-brand-teal/90"
            onClick={onExecute}
          >
            {executing ? <Spinner /> : <Play className="size-3.5" fill="currentColor" />}
            Execute
          </Button>
        </div>
      </div>

      <Textarea
        value={sql}
        onChange={(event) => onSqlChange(event.target.value)}
        readOnly={!isEditing}
        spellCheck={false}
        aria-label="Generated SQL query"
        className={cn(
          'min-h-24 resize-y bg-background font-mono text-sm leading-relaxed',
          !isEditing && 'cursor-default opacity-80',
        )}
      />

      {executeError ? (
        <p className="mt-3 text-sm text-destructive">{executeError}</p>
      ) : null}

      {result ? <SqlResultTable result={result} /> : null}
    </div>
  )
}

function SqlResultTable({ result }: { result: SqlExecuteResponse }) {
  const { columns, rows, row_count: rowCount } = result

  if (columns.length === 0 && rows.length === 0) {
    return (
      <p className="mt-3 text-sm text-muted-foreground">
        Query ran successfully. {rowCount} {rowCount === 1 ? 'row' : 'rows'} returned.
      </p>
    )
  }

  return (
    <div className="mt-3 overflow-hidden rounded-lg border bg-background">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            {columns.map((column) => (
              <TableHead key={column} className="h-auto px-3 py-2 text-xs">
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
                  <TableCell key={column} className="px-3 py-2 text-sm">
                    {formatCellValue(row[column])}
                  </TableCell>
                ))}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
      <p className="border-t px-3 py-2 text-xs text-muted-foreground">
        {rowCount} {rowCount === 1 ? 'row' : 'rows'}
      </p>
    </div>
  )
}
