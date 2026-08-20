export type SqlGenerateRequest = {
  question: string
}

export type SqlGenerateResponse = {
  sql: string
  attempt_id: string
}

export type SqlExecuteRequest = {
  sql: string
  attempt_id: string
}

export type SqlExecuteResponse = {
  columns: string[]
  rows: Record<string, unknown>[]
  row_count: number
}
