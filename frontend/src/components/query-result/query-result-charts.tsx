import { useMemo } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  Scatter,
  ScatterChart,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts'

import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import {
  formatAxisLabel,
  formatNumber,
  formatQueryValue,
  parseNumericValue,
  parseTemporalValue,
} from '@/lib/query-result/format-value'
import type {
  ChartVisualizationType,
  QueryResultData,
  VisualizationRecommendation,
} from '@/lib/query-result/types'
import { cn } from '@/lib/utils'

const CHART_COLORS = [
  'var(--color-brand-teal)',
  'var(--color-brand-sky-blue)',
  'var(--color-brand-orange)',
  'var(--color-brand-navy)',
  'hsl(var(--brand-teal) / 0.55)',
  'hsl(var(--brand-sky-blue) / 0.55)',
  'hsl(var(--brand-orange) / 0.55)',
  'hsl(var(--brand-navy) / 0.55)',
] as const

type QueryResultChartProps = {
  data: QueryResultData
  recommendation: VisualizationRecommendation
  type: ChartVisualizationType
  className?: string
}

type ChartRow = Record<string, string | number>

type SeriesDef = {
  key: string
  label: string
  color: string
}

function toSafeKey(column: string, index: number): string {
  const safe = column
    .replace(/[^a-zA-Z0-9_-]/g, '_')
    .replace(/^([^a-zA-Z_])/, '_$1')
  return safe || `series_${index}`
}

function categoryLabel(value: unknown): string {
  if (value === null || value === undefined) return '—'
  return formatQueryValue(value)
}

function xSortValue(value: unknown, preferTemporal: boolean): number {
  if (preferTemporal) {
    const date = parseTemporalValue(value)
    if (date) return date.getTime()
  }
  const numeric = parseNumericValue(value)
  if (numeric !== null) return numeric
  return 0
}

function buildMeasureSeries(
  valueColumns: string[],
): SeriesDef[] {
  return valueColumns.map((column, index) => ({
    key: toSafeKey(column, index),
    label: column,
    color: CHART_COLORS[index % CHART_COLORS.length],
  }))
}

function buildColorSeries(
  data: QueryResultData,
  colorColumn: string,
): SeriesDef[] {
  const seen = new Map<string, SeriesDef>()
  for (const row of data.rows) {
    const label = categoryLabel(row[colorColumn])
    if (seen.has(label)) continue
    const index = seen.size
    seen.set(label, {
      key: toSafeKey(label, index),
      label,
      color: CHART_COLORS[index % CHART_COLORS.length],
    })
    if (seen.size >= CHART_COLORS.length * 2) break
  }
  return [...seen.values()]
}

function toCartesianRows(
  data: QueryResultData,
  recommendation: VisualizationRecommendation,
  series: SeriesDef[],
  mode: 'measure' | 'color',
  preferTemporalX: boolean,
): ChartRow[] {
  const labelKey = recommendation.labelColumn
  const primaryValue = recommendation.valueColumns[0]

  if (mode === 'color' && recommendation.colorColumn && primaryValue) {
    const colorColumn = recommendation.colorColumn
    const byX = new Map<string, ChartRow>()

    data.rows.forEach((row, index) => {
      const rawLabel = labelKey ? row[labelKey] : index + 1
      const xKey = categoryLabel(rawLabel)
      let entry = byX.get(xKey)
      if (!entry) {
        entry = {
          __index: byX.size,
          __sort: xSortValue(rawLabel, preferTemporalX),
          __label: formatAxisLabel(rawLabel, 24),
          __labelDisplay: formatQueryValue(rawLabel),
        }
        byX.set(xKey, entry)
      }

      const seriesLabel = categoryLabel(row[colorColumn])
      const seriesDef = series.find((item) => item.label === seriesLabel)
      if (!seriesDef) return
      entry[seriesDef.key] = parseNumericValue(row[primaryValue]) ?? 0
    })

    return [...byX.values()].sort((a, b) => Number(a.__sort) - Number(b.__sort))
  }

  const rows: ChartRow[] = data.rows.map((row, index) => {
    const entry: ChartRow = { __index: index }
    const rawLabel = labelKey ? row[labelKey] : index + 1
    entry.__sort = xSortValue(rawLabel, preferTemporalX)
    entry.__label = formatAxisLabel(rawLabel, 24)
    entry.__labelDisplay = formatQueryValue(rawLabel)
    entry.__legendKey = `slice_${index}`

    for (const item of series) {
      const column = recommendation.valueColumns.find(
        (name, i) => toSafeKey(name, i) === item.key,
      )
      if (!column) continue
      entry[item.key] = parseNumericValue(row[column]) ?? 0
    }

    return entry
  })

  return rows.sort((a, b) => Number(a.__sort) - Number(b.__sort))
}

function toScatterPoints(
  data: QueryResultData,
  recommendation: VisualizationRecommendation,
  preferTemporalX: boolean,
): Map<string, Array<{ x: number; y: number; label: string; colorLabel: string }>> {
  const labelKey = recommendation.labelColumn
  const valueKey = recommendation.valueColumns[0]
  const colorColumn = recommendation.colorColumn
  const groups = new Map<
    string,
    Array<{ x: number; y: number; label: string; colorLabel: string }>
  >()

  if (!labelKey || !valueKey) return groups

  data.rows.forEach((row) => {
    const rawX = row[labelKey]
    const x = preferTemporalX
      ? (parseTemporalValue(rawX)?.getTime() ?? parseNumericValue(rawX))
      : parseNumericValue(rawX)
    const y = parseNumericValue(row[valueKey])
    if (x === null || y === null) return

    const colorLabel = colorColumn ? categoryLabel(row[colorColumn]) : 'value'
    const points = groups.get(colorLabel) ?? []
    points.push({
      x,
      y,
      label: formatQueryValue(rawX),
      colorLabel,
    })
    groups.set(colorLabel, points)
  })

  for (const points of groups.values()) {
    points.sort((a, b) => a.x - b.x)
  }

  return groups
}

function buildConfig(series: SeriesDef[]): ChartConfig {
  return Object.fromEntries(
    series.map((item) => [
      item.key,
      {
        label: item.label,
        color: item.color,
      },
    ]),
  )
}

function buildPieConfig(chartData: ChartRow[]): ChartConfig {
  return Object.fromEntries(
    chartData.map((row, index) => [
      String(row.__legendKey),
      {
        label: String(row.__labelDisplay),
        color: CHART_COLORS[index % CHART_COLORS.length],
      },
    ]),
  )
}

function formatXTick(value: unknown, preferTemporal: boolean): string {
  if (preferTemporal && typeof value === 'number') {
    const date = new Date(value)
    if (!Number.isNaN(date.getTime())) {
      return formatAxisLabel(date.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
      }), 10)
    }
  }
  if (typeof value === 'number') return formatNumber(value)
  return formatAxisLabel(value, 10)
}

export function QueryResultChart({
  data,
  recommendation,
  type,
  className,
}: QueryResultChartProps) {
  const preferTemporalX = useMemo(() => {
    if (!recommendation.labelColumn) return false
    return data.rows.some((row) =>
      Boolean(parseTemporalValue(row[recommendation.labelColumn!])),
    )
  }, [data.rows, recommendation.labelColumn])

  const colorMode = Boolean(recommendation.colorColumn) && type !== 'pie'

  const series = useMemo(() => {
    if (colorMode && recommendation.colorColumn) {
      return buildColorSeries(data, recommendation.colorColumn)
    }
    return buildMeasureSeries(recommendation.valueColumns)
  }, [colorMode, data, recommendation.colorColumn, recommendation.valueColumns])

  const chartData = useMemo(() => {
    if (type === 'scatter') return []
    return toCartesianRows(
      data,
      recommendation,
      series,
      colorMode ? 'color' : 'measure',
      preferTemporalX,
    )
  }, [data, recommendation, series, colorMode, preferTemporalX, type])

  const scatterGroups = useMemo(() => {
    if (type !== 'scatter') return new Map()
    return toScatterPoints(data, recommendation, preferTemporalX)
  }, [type, data, recommendation, preferTemporalX])

  const scatterSeries = useMemo(() => {
    if (type !== 'scatter') return series
    if (!recommendation.colorColumn) {
      return [
        {
          key: 'value',
          label: recommendation.valueColumns[0] ?? 'value',
          color: CHART_COLORS[0],
        },
      ]
    }
    return [...scatterGroups.keys()].map((label, index) => ({
      key: toSafeKey(label, index),
      label,
      color: CHART_COLORS[index % CHART_COLORS.length],
    }))
  }, [type, series, recommendation.colorColumn, recommendation.valueColumns, scatterGroups])

  const config = useMemo(() => {
    if (type === 'pie') return buildPieConfig(chartData)
    if (type === 'scatter') return buildConfig(scatterSeries)
    return buildConfig(series)
  }, [type, chartData, scatterSeries, series])

  const hasScatter =
    type === 'scatter' &&
    [...scatterGroups.values()].some((points) => points.length > 0)
  const hasCartesian = type !== 'scatter' && chartData.length > 0 && series.length > 0

  if ((type === 'scatter' && !hasScatter) || (type !== 'scatter' && !hasCartesian)) {
    return (
      <p className="px-3 py-6 text-center text-sm text-muted-foreground">
        Not enough data to render a chart.
      </p>
    )
  }

  const primaryKey = series[0]?.key
  const encodingHint = [
    recommendation.labelColumn && `x: ${recommendation.labelColumn}`,
    recommendation.valueColumns[0] && `y: ${recommendation.valueColumns[0]}`,
    recommendation.colorColumn && `color: ${recommendation.colorColumn}`,
  ]
    .filter(Boolean)
    .join(' · ')

  return (
    <div className={cn('rounded-lg border bg-background p-3', className)}>
      <ChartContainer
        config={config}
        className="aspect-[16/9] max-h-72 w-full min-h-52"
        initialDimension={{ width: 420, height: 240 }}
      >
        {type === 'bar' ? (
          <BarChart data={chartData} margin={{ left: 4, right: 8, top: 8, bottom: 0 }}>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="__label"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              interval="preserveStartEnd"
              tickFormatter={(value) => formatAxisLabel(value, 12)}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              width={44}
              tickFormatter={(value) =>
                typeof value === 'number' ? formatNumber(value) : String(value)
              }
            />
            <ChartTooltip
              content={
                <ChartTooltipContent
                  labelFormatter={(_, payload) => {
                    const display = payload?.[0]?.payload?.__labelDisplay
                    return display != null ? String(display) : ''
                  }}
                />
              }
            />
            {series.length > 1 ? <ChartLegend content={<ChartLegendContent />} /> : null}
            {series.map((item) => (
              <Bar
                key={item.key}
                dataKey={item.key}
                fill={`var(--color-${item.key})`}
                radius={[4, 4, 0, 0]}
                maxBarSize={36}
              />
            ))}
          </BarChart>
        ) : null}

        {type === 'line' ? (
          <LineChart data={chartData} margin={{ left: 4, right: 8, top: 8, bottom: 0 }}>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="__label"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              interval="preserveStartEnd"
              tickFormatter={(value) => formatAxisLabel(value, 10)}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              width={44}
              tickFormatter={(value) =>
                typeof value === 'number' ? formatNumber(value) : String(value)
              }
            />
            <ChartTooltip
              content={
                <ChartTooltipContent
                  labelFormatter={(_, payload) => {
                    const display = payload?.[0]?.payload?.__labelDisplay
                    return display != null ? String(display) : ''
                  }}
                />
              }
            />
            {series.length > 1 ? <ChartLegend content={<ChartLegendContent />} /> : null}
            {series.map((item) => (
              <Line
                key={item.key}
                type="monotone"
                dataKey={item.key}
                stroke={`var(--color-${item.key})`}
                strokeWidth={2}
                dot={{ r: 3 }}
                activeDot={{ r: 4 }}
                connectNulls
              />
            ))}
          </LineChart>
        ) : null}

        {type === 'scatter' ? (
          <ScatterChart margin={{ left: 4, right: 8, top: 8, bottom: 0 }}>
            <CartesianGrid vertical={false} />
            <XAxis
              type="number"
              dataKey="x"
              name={recommendation.labelColumn}
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              tickFormatter={(value) => formatXTick(value, preferTemporalX)}
              domain={['auto', 'auto']}
            />
            <YAxis
              type="number"
              dataKey="y"
              name={recommendation.valueColumns[0]}
              tickLine={false}
              axisLine={false}
              width={44}
              tickFormatter={(value) =>
                typeof value === 'number' ? formatNumber(value) : String(value)
              }
            />
            <ZAxis range={[48, 48]} />
            <ChartTooltip
              cursor={{ strokeDasharray: '4 4' }}
              content={
                <ChartTooltipContent
                  labelFormatter={(_, payload) => {
                    const point = payload?.[0]?.payload as
                      | { label?: string; colorLabel?: string }
                      | undefined
                    if (!point) return ''
                    return point.colorLabel && recommendation.colorColumn
                      ? `${point.colorLabel} · ${point.label ?? ''}`
                      : String(point.label ?? '')
                  }}
                  formatter={(value) =>
                    typeof value === 'number' ? formatNumber(value) : String(value)
                  }
                />
              }
            />
            {scatterSeries.map((item) => (
              <Scatter
                key={item.key}
                name={item.label}
                data={scatterGroups.get(item.label) ?? []}
                fill={item.color}
                fillOpacity={0.85}
              />
            ))}
          </ScatterChart>
        ) : null}

        {type === 'pie' && primaryKey ? (
          <PieChart>
            <ChartTooltip
              content={
                <ChartTooltipContent
                  nameKey="__legendKey"
                  labelFormatter={(_, payload) => {
                    const display = payload?.[0]?.payload?.__labelDisplay
                    return display != null ? String(display) : ''
                  }}
                />
              }
            />
            <Pie
              data={chartData}
              dataKey={primaryKey}
              nameKey="__legendKey"
              innerRadius="48%"
              outerRadius="78%"
              paddingAngle={2}
              strokeWidth={2}
            >
              {chartData.map((row) => (
                <Cell
                  key={String(row.__legendKey)}
                  fill={`var(--color-${String(row.__legendKey)})`}
                />
              ))}
            </Pie>
            <ChartLegend content={<ChartLegendContent nameKey="__legendKey" />} />
          </PieChart>
        ) : null}
      </ChartContainer>
      {type === 'scatter' && scatterSeries.length > 1 ? (
        <div className="mt-2 flex flex-wrap items-center justify-center gap-3">
          {scatterSeries.map((item) => (
            <div
              key={item.key}
              className="flex items-center gap-1.5 text-xs text-muted-foreground"
            >
              <span
                className="size-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: item.color }}
                aria-hidden
              />
              <span className="truncate max-w-28">{item.label}</span>
            </div>
          ))}
        </div>
      ) : null}
      {encodingHint ? (
        <p className="mt-2 truncate text-center text-xs text-muted-foreground">
          {encodingHint}
        </p>
      ) : null}
    </div>
  )
}
