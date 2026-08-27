export type QueryResultData = {
  columns: string[]
  rows: Record<string, unknown>[]
  row_count?: number
}

export type ColumnKind =
  | 'numeric'
  | 'temporal'
  | 'categorical'
  | 'text'
  | 'boolean'
  | 'unknown'

export type ChartVisualizationType = 'bar' | 'line' | 'pie' | 'scatter'

export type VisualizationType = 'table' | 'kpi' | ChartVisualizationType

export type ColumnProfile = {
  name: string
  kind: ColumnKind
  uniqueCount: number
  nullCount: number
  sampleCount: number
}

export type VisualizationRecommendation = {
  type: VisualizationType
  /** X-axis / category labels */
  labelColumn?: string
  /** Y-axis measure(s); when colorColumn is set, typically the first is used */
  valueColumns: string[]
  /** Optional categorical field mapped to color / series */
  colorColumn?: string
  /** Chart types the user can switch between for this result */
  availableChartTypes: ChartVisualizationType[]
  allowTableToggle: boolean
  reason: string
}
