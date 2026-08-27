import { format, isValid, parseISO } from 'date-fns'

const ISO_DATE_RE =
  /^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?(?:Z|[+-]\d{2}:?\d{2})?)?$/
const NUMERIC_STRING_RE = /^-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/

export function isNullish(value: unknown): value is null | undefined {
  return value === null || value === undefined
}

export function parseNumericValue(value: unknown): number | null {
  if (isNullish(value) || typeof value === 'boolean') return null
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null
  }
  if (typeof value === 'bigint') {
    const asNumber = Number(value)
    return Number.isFinite(asNumber) ? asNumber : null
  }
  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (!trimmed || !NUMERIC_STRING_RE.test(trimmed)) return null
    const parsed = Number(trimmed)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

export function parseTemporalValue(value: unknown): Date | null {
  if (isNullish(value)) return null

  if (value instanceof Date) {
    return isValid(value) ? value : null
  }

  if (typeof value === 'number' && Number.isFinite(value)) {
    // Prefer year-like numbers over epoch millis for column inference elsewhere.
    if (value > 1e11) {
      const fromEpoch = new Date(value)
      return isValid(fromEpoch) ? fromEpoch : null
    }
    return null
  }

  if (typeof value !== 'string') return null

  const trimmed = value.trim()
  if (!trimmed || !ISO_DATE_RE.test(trimmed)) return null

  const parsed = parseISO(trimmed.includes(' ') ? trimmed.replace(' ', 'T') : trimmed)
  return isValid(parsed) ? parsed : null
}

export function formatNumber(value: number): string {
  const abs = Math.abs(value)
  const maximumFractionDigits =
    Number.isInteger(value) || abs >= 1000 ? 0 : abs >= 1 ? 2 : 4

  return new Intl.NumberFormat(undefined, {
    maximumFractionDigits,
  }).format(value)
}

export function formatDateTime(value: Date): string {
  const hasTime =
    value.getUTCHours() !== 0 ||
    value.getUTCMinutes() !== 0 ||
    value.getUTCSeconds() !== 0 ||
    value.getUTCMilliseconds() !== 0

  return format(value, hasTime ? 'MMM d, yyyy HH:mm' : 'MMM d, yyyy')
}

/** Pretty-print query cell values for tables, tooltips, and KPI labels. */
export function formatQueryValue(value: unknown): string {
  if (isNullish(value)) return '—'

  if (typeof value === 'boolean') return value ? 'Yes' : 'No'

  const temporal = parseTemporalValue(value)
  if (temporal) return formatDateTime(temporal)

  const numeric = parseNumericValue(value)
  if (numeric !== null && typeof value !== 'string') {
    return formatNumber(numeric)
  }
  if (numeric !== null && typeof value === 'string' && NUMERIC_STRING_RE.test(value.trim())) {
    return formatNumber(numeric)
  }

  if (typeof value === 'object') {
    try {
      return JSON.stringify(value)
    } catch {
      return String(value)
    }
  }

  return String(value)
}

export function formatAxisLabel(value: unknown, maxLength = 18): string {
  const formatted = formatQueryValue(value)
  if (formatted.length <= maxLength) return formatted
  return `${formatted.slice(0, maxLength - 1)}…`
}
