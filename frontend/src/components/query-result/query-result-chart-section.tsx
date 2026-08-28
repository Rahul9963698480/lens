import { BarChart3, ChartScatter, LineChart, PieChart } from 'lucide-react'
import { useEffect, useState } from 'react'

import { QueryResultChart } from '@/components/query-result/query-result-charts'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type {
  ChartVisualizationType,
  QueryResultData,
  VisualizationRecommendation,
} from '@/lib/query-result/types'
import { cn } from '@/lib/utils'

const CHART_TYPE_META: Record<
  ChartVisualizationType,
  { label: string; icon: typeof BarChart3 }
> = {
  bar: { label: 'Bar chart', icon: BarChart3 },
  line: { label: 'Line chart', icon: LineChart },
  pie: { label: 'Pie chart', icon: PieChart },
  scatter: { label: 'Scatter chart', icon: ChartScatter },
}

function defaultChartType(
  recommendation: VisualizationRecommendation,
): ChartVisualizationType | null {
  const { availableChartTypes, type } = recommendation
  if (availableChartTypes.length === 0) return null
  if (
    type !== 'table' &&
    type !== 'kpi' &&
    availableChartTypes.includes(type)
  ) {
    return type
  }
  return availableChartTypes[0]
}

type QueryResultChartSectionProps = {
  data: QueryResultData
  recommendation: VisualizationRecommendation
  className?: string
}

export function QueryResultChartSection({
  data,
  recommendation,
  className,
}: QueryResultChartSectionProps) {
  const availableTypes = recommendation.availableChartTypes
  const [selectedType, setSelectedType] = useState<ChartVisualizationType>(
    () => defaultChartType(recommendation) ?? 'bar',
  )

  useEffect(() => {
    const next = defaultChartType(recommendation)
    if (next) setSelectedType(next)
  }, [recommendation])

  if (availableTypes.length === 0) {
    return null
  }

  const activeType = availableTypes.includes(selectedType)
    ? selectedType
    : (defaultChartType(recommendation) ?? availableTypes[0])
  const meta = CHART_TYPE_META[activeType]
  const Icon = meta.icon

  return (
    <section className={cn('flex min-w-0 flex-col gap-3', className)}>
      {availableTypes.length > 1 ? (
        <Select
          value={activeType}
          onValueChange={(value) => {
            if (value) setSelectedType(value as ChartVisualizationType)
          }}
        >
          <SelectTrigger size="sm" className="w-fit min-w-40">
            <SelectValue placeholder="Select chart type">
              <span className="flex items-center gap-1.5">
                <Icon className="size-3.5" />
                {meta.label}
              </span>
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            {availableTypes.map((type) => {
              const itemMeta = CHART_TYPE_META[type]
              const ItemIcon = itemMeta.icon
              return (
                <SelectItem key={type} value={type}>
                  <ItemIcon className="size-3.5" />
                  {itemMeta.label}
                </SelectItem>
              )
            })}
          </SelectContent>
        </Select>
      ) : (
        <p className="flex items-center gap-1.5 text-xs font-medium tracking-wide text-muted-foreground uppercase">
          <Icon className="size-3.5" />
          {meta.label}
        </p>
      )}

      <QueryResultChart
        data={data}
        recommendation={recommendation}
        type={activeType}
      />
    </section>
  )
}
