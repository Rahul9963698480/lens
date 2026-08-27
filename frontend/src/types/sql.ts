export type SqlExecuteResponse = {
  columns: string[]
  rows: Record<string, unknown>[]
  row_count: number
}
