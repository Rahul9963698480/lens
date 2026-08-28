import { AlertCircle, Inbox } from 'lucide-react'
import { useMemo } from 'react'

import { QueryResultChartSection } from '@/components/query-result/query-result-chart-section'
import { QueryResultKpi } from '@/components/query-result/query-result-kpi'
import { QueryResultTable } from '@/components/query-result/query-result-table'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from '@/components/ui/empty'
import { Skeleton } from '@/components/ui/skeleton'
import { Spinner } from '@/components/ui/spinner'
import { inferVisualization } from '@/lib/query-result/infer-visualization'
import type { QueryResultData } from '@/lib/query-result/types'
import { cn } from '@/lib/utils'

export type QueryResultViewMode = 'table' | 'visualization'

type QueryResultRendererProps = {
  data?: QueryResultData | null
  loading?: boolean
  error?: string | null
  className?: string
  /** Controlled by the Visualization button beside Execute. */
  viewMode?: QueryResultViewMode
}

function QueryResultLoading({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'flex flex-col gap-3 rounded-lg border bg-background p-3',
        className,
      )}
      role="status"
      aria-live="polite"
      aria-label="Loading query results"
    >
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner className="size-4" />
        Running query…
      </div>
      <Skeleton className="h-8 w-full" />
      <Skeleton className="h-8 w-11/12" />
      <Skeleton className="h-8 w-4/5" />
      <Skeleton className="h-24 w-full" />
    </div>
  )
}

function QueryResultEmpty({ className }: { className?: string }) {
  return (
    <Empty className={cn('min-h-36 border border-dashed bg-background', className)}>
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <Inbox />
        </EmptyMedia>
        <EmptyTitle>No data returned</EmptyTitle>
        <EmptyDescription>
          The query completed successfully but returned no rows to display.
        </EmptyDescription>
      </EmptyHeader>
    </Empty>
  )
}

function QueryResultError({
  message,
  className,
}: {
  message: string
  className?: string
}) {
  return (
    <Alert variant="destructive" className={cn('bg-background', className)}>
      <AlertCircle />
      <AlertTitle>Query failed</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  )
}

/**
 * Renders tabular query results. Table is the default; visualization mode
 * shows one chart at a time with a chart-type dropdown.
 */
export function QueryResultRenderer({
  data,
  loading = false,
  error = null,
  className,
  viewMode = 'table',
}: QueryResultRendererProps) {
  const recommendation = useMemo(
    () => (data ? inferVisualization(data) : null),
    [data],
  )

  if (loading && !data) {
    return <QueryResultLoading className={className} />
  }

  if (error) {
    return <QueryResultError message={error} className={className} />
  }

  if (!data) {
    return null
  }

  const rowCount = data.row_count ?? data.rows.length
  const isEmpty =
    data.rows.length === 0 && (data.columns.length === 0 || rowCount === 0)

  if (isEmpty) {
    return <QueryResultEmpty className={className} />
  }

  if (!recommendation) {
    return null
  }

  const availableTypes = recommendation.availableChartTypes
  const showKpi = viewMode === 'visualization' && recommendation.type === 'kpi'
  const showCharts = viewMode === 'visualization' && availableTypes.length > 0
  const hasVisualizations = showKpi || showCharts

  return (
    <div className={cn('flex w-full min-w-0 flex-col gap-3', className)}>
      {loading ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Spinner className="size-3.5" />
          Refreshing results…
        </div>
      ) : null}

      {viewMode === 'visualization' ? (
        hasVisualizations ? (
          <div className="flex flex-col gap-4">
            {showKpi ? (
              <section className="flex flex-col gap-1.5">
                <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                  KPI
                </p>
                <QueryResultKpi data={data} recommendation={recommendation} />
              </section>
            ) : null}

            {showCharts ? (
              <QueryResultChartSection
                data={data}
                recommendation={recommendation}
              />
            ) : null}

            <div className="flex flex-col gap-1.5">
              <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                Data
              </p>
              <QueryResultTable data={data} />
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-3 rounded-lg border border-dashed bg-background p-4">
            <p className="text-sm text-muted-foreground">
              No chart visualizations are available for this result. Showing the
              data table instead.
            </p>
            <QueryResultTable data={data} />
          </div>
        )
      ) : (
        <QueryResultTable data={data} />
      )}
    </div>
  )
}

export type { QueryResultRendererProps }
