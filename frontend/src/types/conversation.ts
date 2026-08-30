import type { AnalysisRunResponse } from '@/types/analysis'

export type PlaygroundConversation = {
  id: string
  project_id: string
  title: string
  created_at: string
  updated_at: string
}

export type PlaygroundMessage = {
  id: string
  conversation_id: string
  question: string
  sql: string
  answer: string
  analysis_id: string | null
  queries_used: AnalysisRunResponse['queries_used'] | null
  created_at: string
}

export type PlaygroundConversationDetail = PlaygroundConversation & {
  messages: PlaygroundMessage[]
}
