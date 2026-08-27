import { BarChart3, Check, Pencil, Play, X } from 'lucide-react'
import { useEffect, useState } from 'react'

import {
  QueryResultRenderer,
  type QueryResultViewMode,
} from '@/components/query-result'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { Textarea } from '@/components/ui/textarea'
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
  const [viewMode, setViewMode] = useState<QueryResultViewMode>('table')
  const canExecute = sql.trim().length > 0 && !executing
  const canVisualize = Boolean(result) && !executing && !executeError

  useEffect(() => {
    setViewMode('table')
  }, [result, executeError])

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
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={!canVisualize}
            aria-pressed={viewMode === 'visualization'}
            className={cn(
              'border-brand-teal/40 text-brand-teal hover:bg-brand-teal/10 hover:text-brand-teal',
              viewMode === 'visualization' &&
                'border-brand-teal bg-brand-teal/10',
            )}
            onClick={() =>
              setViewMode((current) =>
                current === 'visualization' ? 'table' : 'visualization',
              )
            }
          >
            <BarChart3 className="size-3.5" />
            Visualization
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

      {executing || executeError || result ? (
        <QueryResultRenderer
          className="mt-3"
          data={result}
          loading={executing}
          error={executeError}
          viewMode={viewMode}
        />
      ) : null}
    </div>
  )
}
