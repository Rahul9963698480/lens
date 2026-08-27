import {
  isNullish,
  parseNumericValue,
  parseTemporalValue,
} from '@/lib/query-result/format-value'
import type {
  ChartVisualizationType,
  ColumnKind,
  ColumnProfile,
  QueryResultData,
  VisualizationRecommendation,
} from '@/lib/query-result/types'

const MAX_CHART_CATEGORIES = 24
const MAX_PIE_CATEGORIES = 8
const MAX_COLOR_CATEGORIES = 12
const SAMPLE_LIMIT = 100

function sampleValues(rows: Record<string, unknown>[], column: string): unknown[] {
  const values: unknown[] = []
  for (const row of rows.slice(0, SAMPLE_LIMIT)) {
    values.push(row[column])
  }
  return values
}

function inferColumnKind(values: unknown[]): ColumnKind {
  const nonNull = values.filter((value) => !isNullish(value))
  if (nonNull.length === 0) return 'unknown'

  let numeric = 0
  let temporal = 0
  let booleanish = 0
  let textual = 0

  for (const value of nonNull) {
    if (typeof value === 'boolean') {
      booleanish += 1
      continue
    }

    if (parseTemporalValue(value)) {
      temporal += 1
      continue
    }

    if (parseNumericValue(value) !== null) {
      numeric += 1
      continue
    }

    textual += 1
  }

  const total = nonNull.length
  const majority = (count: number) => count / total >= 0.7

  if (majority(booleanish)) return 'boolean'
  if (majority(temporal)) return 'temporal'
  if (majority(numeric)) return 'numeric'
  if (majority(textual)) {
    const unique = new Set(
      nonNull.map((value) =>
        typeof value === 'string' ? value.trim() : String(value),
      ),
    ).size
    return unique <= Math.min(MAX_CHART_CATEGORIES, Math.max(total * 0.6, 2))
      ? 'categorical'
      : 'text'
  }

  return 'unknown'
}

export function profileColumns(data: QueryResultData): ColumnProfile[] {
  return data.columns.map((name) => {
    const values = sampleValues(data.rows, name)
    const nonNull = values.filter((value) => !isNullish(value))
    const unique = new Set(
      nonNull.map((value) => {
        if (typeof value === 'object') {
          try {
            return JSON.stringify(value)
          } catch {
            return String(value)
          }
        }
        return String(value)
      }),
    )

    return {
      name,
      kind: inferColumnKind(values),
      uniqueCount: unique.size,
      nullCount: values.length - nonNull.length,
      sampleCount: values.length,
    }
  })
}

function isChartableCategory(profile: ColumnProfile, rowCount: number): boolean {
  if (profile.kind === 'categorical' || profile.kind === 'boolean') return true
  if (profile.kind === 'text') {
    return (
      profile.uniqueCount > 0 &&
      profile.uniqueCount <= Math.min(MAX_CHART_CATEGORIES, rowCount)
    )
  }
  return false
}

function pickLabelColumn(
  profiles: ColumnProfile[],
  preferred: ColumnKind[],
  rowCount: number,
): ColumnProfile | undefined {
  for (const kind of preferred) {
    const match = profiles.find((profile) => {
      if (profile.kind !== kind) return false
      if (kind === 'temporal') return true
      return isChartableCategory(profile, rowCount)
    })
    if (match) return match
  }
  return undefined
}

function pickColorColumn(
  profiles: ColumnProfile[],
  reserved: Set<string>,
  rowCount: number,
): ColumnProfile | undefined {
  return profiles.find((profile) => {
    if (reserved.has(profile.name)) return false
    if (!isChartableCategory(profile, rowCount)) return false
    return (
      profile.uniqueCount >= 2 &&
      profile.uniqueCount <= Math.min(MAX_COLOR_CATEGORIES, rowCount)
    )
  })
}

function allNonNegative(rows: Record<string, unknown>[], column: string): boolean {
  for (const row of rows) {
    const value = parseNumericValue(row[column])
    if (value === null) continue
    if (value < 0) return false
  }
  return true
}

function uniqueTypes(types: ChartVisualizationType[]): ChartVisualizationType[] {
  return [...new Set(types)]
}

/**
 * Choose the best default visualization for a tabular query result.
 * Chart recommendations always allow falling back to a table view.
 */
export function inferVisualization(data: QueryResultData): VisualizationRecommendation {
  const rowCount = data.row_count ?? data.rows.length
  const profiles = profileColumns(data)
  const numericColumns = profiles.filter((profile) => profile.kind === 'numeric')
  const temporalColumns = profiles.filter((profile) => profile.kind === 'temporal')
  const textLikeCount = profiles.filter(
    (profile) =>
      profile.kind === 'text' ||
      profile.kind === 'categorical' ||
      profile.kind === 'unknown',
  ).length

  if (profiles.length === 0 || (rowCount === 0 && data.columns.length === 0)) {
    return {
      type: 'table',
      valueColumns: [],
      availableChartTypes: [],
      allowTableToggle: false,
      reason: 'No columns to visualize',
    }
  }

  // Single important numeric value → KPI
  if (rowCount === 1 && numericColumns.length === 1 && profiles.length <= 3) {
    const valueColumn = numericColumns[0]
    const labelColumn = profiles.find(
      (profile) =>
        profile.name !== valueColumn.name &&
        (profile.kind === 'text' || profile.kind === 'categorical'),
    )

    return {
      type: 'kpi',
      labelColumn: labelColumn?.name,
      valueColumns: [valueColumn.name],
      availableChartTypes: [],
      allowTableToggle: profiles.length > 1,
      reason: 'Single numeric metric',
    }
  }

  if (rowCount === 1 && numericColumns.length >= 1 && profiles.length === 1) {
    return {
      type: 'kpi',
      valueColumns: [numericColumns[0].name],
      availableChartTypes: [],
      allowTableToggle: false,
      reason: 'Single numeric cell',
    }
  }

  // Numeric × numeric → scatter (optional color)
  if (numericColumns.length >= 2 && rowCount >= 2 && temporalColumns.length === 0) {
    const xColumn = numericColumns[0]
    const yColumn = numericColumns[1]
    const colorColumn = pickColorColumn(
      profiles,
      new Set([xColumn.name, yColumn.name]),
      rowCount,
    )
    const available = uniqueTypes([
      'scatter',
      'bar',
      ...(colorColumn ? (['line'] as ChartVisualizationType[]) : []),
    ])

    return {
      type: 'scatter',
      labelColumn: xColumn.name,
      valueColumns: [yColumn.name, ...numericColumns.slice(2, 3).map((c) => c.name)],
      colorColumn: colorColumn?.name,
      availableChartTypes: available,
      allowTableToggle: true,
      reason: colorColumn
        ? 'Numeric relationship with categorical color'
        : 'Numeric × numeric relationship',
    }
  }

  // Time/date + numeric → line (scatter available; color by category when present)
  if (temporalColumns.length > 0 && numericColumns.length > 0 && rowCount >= 2) {
    const labelColumn = temporalColumns[0]
    const reserved = new Set([
      labelColumn.name,
      ...numericColumns.slice(0, 3).map((column) => column.name),
    ])
    const colorColumn = pickColorColumn(profiles, reserved, rowCount)
    const preferScatter = Boolean(colorColumn) && rowCount >= 8

    return {
      type: preferScatter ? 'scatter' : 'line',
      labelColumn: labelColumn.name,
      valueColumns: colorColumn
        ? [numericColumns[0].name]
        : numericColumns.slice(0, 3).map((column) => column.name),
      colorColumn: colorColumn?.name,
      availableChartTypes: uniqueTypes(['line', 'scatter', 'bar']),
      allowTableToggle: true,
      reason: colorColumn
        ? 'Temporal series colored by category'
        : 'Temporal series with numeric values',
    }
  }

  const categoryColumn = pickLabelColumn(
    profiles,
    ['categorical', 'boolean', 'text'],
    rowCount,
  )

  // Categorical + numeric → pie (composition) or bar
  if (categoryColumn && numericColumns.length > 0 && rowCount >= 2) {
    const valueColumn = numericColumns[0]
    const distinct = categoryColumn.uniqueCount
    const fitsPie =
      numericColumns.length === 1 &&
      distinct >= 2 &&
      distinct <= MAX_PIE_CATEGORIES &&
      distinct === rowCount &&
      allNonNegative(data.rows, valueColumn.name)

    const colorColumn = pickColorColumn(
      profiles,
      new Set([
        categoryColumn.name,
        ...numericColumns.slice(0, 3).map((column) => column.name),
      ]),
      rowCount,
    )

    const available: ChartVisualizationType[] = ['bar']
    if (fitsPie) available.push('pie')
    if (rowCount >= 3) available.push('scatter')
    if (colorColumn || numericColumns.length > 1) available.push('line')

    if (fitsPie) {
      return {
        type: 'pie',
        labelColumn: categoryColumn.name,
        valueColumns: [valueColumn.name],
        availableChartTypes: uniqueTypes(available),
        allowTableToggle: true,
        reason: 'Categorical composition',
      }
    }

    if (distinct <= MAX_CHART_CATEGORIES) {
      return {
        type: 'bar',
        labelColumn: categoryColumn.name,
        valueColumns: colorColumn
          ? [valueColumn.name]
          : numericColumns.slice(0, 3).map((column) => column.name),
        colorColumn: colorColumn?.name,
        availableChartTypes: uniqueTypes(available),
        allowTableToggle: true,
        reason: colorColumn
          ? 'Categorical values with color encoding'
          : 'Categorical values with numeric measures',
      }
    }
  }

  // Mostly text → table
  if (textLikeCount >= Math.ceil(profiles.length * 0.6) || numericColumns.length === 0) {
    return {
      type: 'table',
      valueColumns: [],
      availableChartTypes: [],
      allowTableToggle: false,
      reason: 'Mostly textual columns',
    }
  }

  return {
    type: 'table',
    valueColumns: numericColumns.map((column) => column.name),
    availableChartTypes: [],
    allowTableToggle: false,
    reason: 'Default tabular view',
  }
}
