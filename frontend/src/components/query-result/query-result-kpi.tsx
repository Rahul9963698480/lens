import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { formatQueryValue } from '@/lib/query-result/format-value'
import type { QueryResultData, VisualizationRecommendation } from '@/lib/query-result/types'
import { cn } from '@/lib/utils'

type QueryResultKpiProps = {
  data: QueryResultData
  recommendation: VisualizationRecommendation
  className?: string
}

export function QueryResultKpi({ data, recommendation, className }: QueryResultKpiProps) {
  const row = data.rows[0] ?? {}
  const valueKey = recommendation.valueColumns[0]
  const labelKey = recommendation.labelColumn
  const value = valueKey ? formatQueryValue(row[valueKey]) : '—'
  const contextLabel = labelKey ? formatQueryValue(row[labelKey]) : null

  return (
    <Card
      size="sm"
      className={cn(
        'border-border/80 bg-background shadow-none ring-1 ring-border/60',
        className,
      )}
    >
      <CardHeader className="pb-0">
        <CardDescription className="truncate text-xs tracking-wide uppercase">
          {valueKey ?? 'Metric'}
        </CardDescription>
        {contextLabel ? (
          <CardTitle className="truncate text-sm font-medium text-muted-foreground">
            {contextLabel}
          </CardTitle>
        ) : null}
      </CardHeader>
      <CardContent>
        <p className="text-3xl font-semibold tracking-tight text-foreground tabular-nums">
          {value}
        </p>
      </CardContent>
    </Card>
  )
}
