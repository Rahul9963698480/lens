import type { SchemaColumn } from '@/types/project'

export function getColumnType(column: SchemaColumn): string {
  return column.type ?? column.inferred_type ?? 'unknown'
}

export function formatColumnType(type: string | null | undefined): string {
  if (!type) return 'UNKNOWN'

  const normalized = type.toLowerCase()

  if (normalized.includes('character varying') || normalized === 'character') {
    return 'TEXT'
  }

  if (normalized === 'integer' || normalized === 'smallint') return 'INTEGER'
  if (normalized.includes('timestamp')) return 'DATETIME'
  if (normalized === 'boolean') return 'BOOLEAN'
  if (normalized === 'date') return 'DATE'
  if (normalized === 'numeric') return 'NUMERIC'
  if (normalized === 'text') return 'TEXT'
  if (normalized === 'objectid') return 'OBJECTID'

  return type.toUpperCase()
}

export function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export function getColumnDisplayFields(columns: SchemaColumn[]) {
  const fields: Array<{
    key: string
    label: string
    getValue: (column: SchemaColumn) => unknown
  }> = []

  const hasType = columns.some(
    (column) => column.type != null || column.inferred_type != null,
  )

  if (hasType) {
    fields.push({
      key: 'type',
      label: 'Type',
      getValue: (column) => column.type ?? column.inferred_type,
    })
  }

  if (columns.some((column) => column.nullable != null)) {
    fields.push({
      key: 'nullable',
      label: 'Nullable',
      getValue: (column) => column.nullable,
    })
  }

  if (columns.some((column) => column.primary_key === true)) {
    fields.push({
      key: 'primary_key',
      label: 'Primary Key',
      getValue: (column) => column.primary_key,
    })
  }

  if (columns.some((column) => column.foreign_key != null && column.foreign_key !== '')) {
    fields.push({
      key: 'foreign_key',
      label: 'Foreign Key',
      getValue: (column) => column.foreign_key,
    })
  }

  if (columns.some((column) => column.presence_pct != null)) {
    fields.push({
      key: 'presence_pct',
      label: 'Presence',
      getValue: (column) => column.presence_pct,
    })
  }

  return fields
}

export function formatColumnAttribute(key: string, value: unknown): string {
  if (value === null || value === undefined || value === false) return '—'

  if (key === 'type') {
    return formatColumnType(String(value))
  }

  if (key === 'presence_pct') {
    return `${value}%`
  }

  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No'
  }

  return String(value)
}
