import { Check, Pencil, X } from 'lucide-react'
import { useMemo, useState } from 'react'

import { QueryResultChartSection } from '@/components/query-result/query-result-chart-section'
import { QueryResultKpi } from '@/components/query-result/query-result-kpi'
import { QueryResultTable } from '@/components/query-result/query-result-table'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { inferVisualization } from '@/lib/query-result/infer-visualization'
import type { QueryResultData } from '@/lib/query-result/types'
import { cn } from '@/lib/utils'
import type { AnalysisQueryUsed, AnalysisRunResponse } from '@/types/analysis'

type SqlFeedback = 'correct' | 'incorrect' | null

type AnalysisResultCardProps = {
  result: AnalysisRunResponse
  className?: string
  onSqlChange?: (attemptId: string, sql: string) => void
  onFeedback?: (attemptId: string, feedback: 'correct' | 'incorrect') => void
}

function toQueryResultData(
  summary: AnalysisRunResponse['queries_used'][number]['result_summary'],
): QueryResultData | null {
  if (summary.status !== 'ok') {
    return null
  }

  return {
    columns: summary.columns,
    rows: summary.rows_preview,
    row_count: summary.row_count,
  }
}

function AnalysisQueryPanel({
  query,
  showLabel,
  index,
  onSqlChange,
  onFeedback,
}: {
  query: AnalysisQueryUsed
  showLabel: boolean
  index: number
  onSqlChange?: (attemptId: string, sql: string) => void
  onFeedback?: (attemptId: string, feedback: 'correct' | 'incorrect') => void
}) {
  const [isEditing, setIsEditing] = useState(false)
  const [feedback, setFeedback] = useState<SqlFeedback>(null)

  const handleFeedback = (value: 'correct' | 'incorrect') => {
    setFeedback(value)
    onFeedback?.(query.attempt_id, value)
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          {showLabel ? `Query ${index + 1}` : 'SQL query'}
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
        </div>
      </div>

      <Textarea
        value={query.sql}
        onChange={(event) => onSqlChange?.(query.attempt_id, event.target.value)}
        readOnly={!isEditing}
        spellCheck={false}
        aria-label="Analysis SQL query"
        className={cn(
          'min-h-24 resize-y bg-background font-mono text-sm leading-relaxed',
          !isEditing && 'cursor-default opacity-80',
        )}
      />
    </div>
  )
}

export function AnalysisResultCard({
  result,
  className,
  onSqlChange,
  onFeedback,
}: AnalysisResultCardProps) {
  const primaryQuery = result.queries_used[0]
  const tableData = primaryQuery ? toQueryResultData(primaryQuery.result_summary) : null
  const recommendation = useMemo(
    () => (tableData ? inferVisualization(tableData) : null),
    [tableData],
  )

  const resultError =
    primaryQuery?.result_summary.status === 'error'
      ? primaryQuery.result_summary.message ?? 'Query failed.'
      : null

  return (
    <div
      className={cn(
        'w-full min-w-0 rounded-xl border border-border/80 bg-muted/40 p-3',
        className,
      )}
    >
      <Tabs defaultValue="analysis">
        <TabsList className="h-auto w-full rounded-full bg-muted p-1">
          <TabsTrigger
            value="analysis"
            className="rounded-full px-3.5 py-1.5 text-sm font-medium text-foreground/70 transition-colors data-active:bg-primary data-active:text-primary-foreground data-active:shadow-sm"
          >
            Analysis
          </TabsTrigger>
          <TabsTrigger
            value="data"
            className="rounded-full px-3.5 py-1.5 text-sm font-medium text-foreground/70 transition-colors data-active:bg-primary data-active:text-primary-foreground data-active:shadow-sm"
          >
            Data
          </TabsTrigger>
          <TabsTrigger
            value="query"
            className="rounded-full px-3.5 py-1.5 text-sm font-medium text-foreground/70 transition-colors data-active:bg-primary data-active:text-primary-foreground data-active:shadow-sm"
          >
            Query
          </TabsTrigger>
          <TabsTrigger
            value="graph"
            className="rounded-full px-3.5 py-1.5 text-sm font-medium text-foreground/70 transition-colors data-active:bg-primary data-active:text-primary-foreground data-active:shadow-sm"
          >
            Graph
          </TabsTrigger>
        </TabsList>

        <TabsContent value="analysis" className="mt-3">
          <p className="text-sm leading-relaxed text-foreground">{result.answer}</p>
        </TabsContent>

        <TabsContent value="data" className="mt-3">
          {resultError ? (
            <Alert variant="destructive" className="bg-background">
              <AlertTitle>Query failed</AlertTitle>
              <AlertDescription>{resultError}</AlertDescription>
            </Alert>
          ) : tableData ? (
            <QueryResultTable data={tableData} />
          ) : (
            <p className="text-sm text-muted-foreground">No data available.</p>
          )}
        </TabsContent>

        <TabsContent value="query" className="mt-3">
          <div className="flex flex-col gap-4">
            {result.queries_used.map((query, index) => (
              <AnalysisQueryPanel
                key={query.attempt_id}
                query={query}
                index={index}
                showLabel={result.queries_used.length > 1}
                onSqlChange={onSqlChange}
                onFeedback={onFeedback}
              />
            ))}
          </div>
        </TabsContent>

        <TabsContent value="graph" className="mt-3">
          {resultError ? (
            <Alert variant="destructive" className="bg-background">
              <AlertTitle>Query failed</AlertTitle>
              <AlertDescription>{resultError}</AlertDescription>
            </Alert>
          ) : tableData && recommendation ? (
            <div className="flex flex-col gap-4">
              {recommendation.type === 'kpi' ? (
                <section className="flex flex-col gap-1.5">
                  <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                    KPI
                  </p>
                  <QueryResultKpi data={tableData} recommendation={recommendation} />
                </section>
              ) : null}

              {recommendation.availableChartTypes.length > 0 ? (
                <QueryResultChartSection
                  data={tableData}
                  recommendation={recommendation}
                />
              ) : (
                <p className="text-sm text-muted-foreground">
                  No chart visualizations are available for this result.
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No data available for charts.</p>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
