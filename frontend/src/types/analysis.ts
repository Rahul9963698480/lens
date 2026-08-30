export type AnalysisStartRequest = {
  question: string
  conversation_id?: string | null
}

export type AnalysisStartResponse = {
  analysis_id: string
  attempt_id: string
  conversation_id: string
  proposed_sql: string
  message: string
}

export type AnalysisResultSummary = {
  status: 'ok' | 'error'
  columns: string[]
  row_count: number
  rows_preview: Record<string, unknown>[]
  message?: string
}

export type AnalysisQueryUsed = {
  attempt_id: string
  sql: string
  result_summary: AnalysisResultSummary
}

export type AnalysisRunResponse = {
  analysis_id: string
  answer: string
  queries_used: AnalysisQueryUsed[]
}
