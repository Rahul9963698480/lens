import type {
  ColumnAnnotationPayload,
  CreateProjectPayload,
  CreateXlsxProjectPayload,
  Project,
  ProjectPreviewResponse,
  ProjectSchemaResponse,
  TableAnnotationPayload,
  TableSchema,
} from '@/types/project'
import type {
  AnalysisRunResponse,
  AnalysisStartRequest,
  AnalysisStartResponse,
} from '@/types/analysis'
import type {
  PlaygroundConversation,
  PlaygroundConversationDetail,
} from '@/types/conversation'
import { config } from '@/config/env'
import { apiErrorMessage } from './error-message'
import axiosInstance from './axios-instance'

type SseEvent = {
  event: string
  data: string
}

function parseSseChunk(buffer: string): { events: SseEvent[]; rest: string } {
  const events: SseEvent[] = []
  const parts = buffer.split('\n\n')
  const rest = parts.pop() ?? ''
  for (const part of parts) {
    let event = 'message'
    const dataLines: string[] = []
    for (const line of part.split('\n')) {
      if (line.startsWith('event:')) {
        event = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trim())
      }
    }
    if (dataLines.length > 0) {
      events.push({ event, data: dataLines.join('\n') })
    }
  }
  return { events, rest }
}

async function runAnalysisStream(
  projectId: string,
  analysisId: string,
  onProgress?: (stage: string, message: string) => void,
  conversationId?: string | null,
): Promise<AnalysisRunResponse> {
  const params = new URLSearchParams({ stream: '1' })
  if (conversationId) {
    params.set('conversation_id', conversationId)
  }
  const url = `${config.apiUrl}/projects/${projectId}/analysis/${analysisId}/run?${params.toString()}`
  const response = await fetch(url, {
    method: 'POST',
    headers: { Accept: 'text/event-stream' },
  })

  if (!response.ok) {
    let body: unknown = null
    try {
      body = await response.json()
    } catch {
      body = null
    }
    throw new Error(apiErrorMessage(body, 'Failed to run analysis.'))
  }

  if (!response.body) {
    throw new Error('Analysis stream is empty.')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let complete: AnalysisRunResponse | null = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }
    buffer += decoder.decode(value, { stream: true })
    const parsed = parseSseChunk(buffer)
    buffer = parsed.rest
    for (const item of parsed.events) {
      let payload: Record<string, unknown> = {}
      try {
        payload = JSON.parse(item.data) as Record<string, unknown>
      } catch {
        payload = {}
      }
      if (item.event === 'progress') {
        onProgress?.(
          String(payload.stage ?? ''),
          String(payload.message ?? ''),
        )
      } else if (item.event === 'complete') {
        complete = payload as unknown as AnalysisRunResponse
      } else if (item.event === 'error') {
        throw new Error(
          apiErrorMessage(payload, 'Failed to run analysis.'),
        )
      }
    }
  }

  if (!complete) {
    throw new Error('Analysis stream ended without a result.')
  }
  return complete
}

const projectsApi = {
  list: () => axiosInstance.get<Project[]>('/projects'),
  create: (payload: CreateProjectPayload) =>
    axiosInstance.post<Project>('/projects', payload),
  uploadXlsx: ({ name, file }: CreateXlsxProjectPayload) => {
    const formData = new FormData()
    formData.append('name', name)
    formData.append('file', file)
    return axiosInstance.post<Project>('/projects/upload-xlsx', formData)
  },
  delete: (projectId: string) =>
    axiosInstance.delete<void>(`/projects/${projectId}`),
  getSchema: (projectId: string) =>
    axiosInstance.get<ProjectSchemaResponse>(`/projects/${projectId}/schema`),
  getPreview: (projectId: string) =>
    axiosInstance.get<ProjectPreviewResponse>(`/projects/${projectId}/preview`),
  updateTableAnnotations: (
    projectId: string,
    tableName: string,
    payload: TableAnnotationPayload,
  ) =>
    axiosInstance.patch<TableSchema>(
      `/projects/${projectId}/schema/${tableName}`,
      payload,
    ),
  updateColumnAnnotations: (
    projectId: string,
    tableName: string,
    columnName: string,
    payload: ColumnAnnotationPayload,
  ) =>
    axiosInstance.patch<TableSchema>(
      `/projects/${projectId}/schema/${tableName}/columns/${columnName}`,
      payload,
    ),
  startAnalysis: (projectId: string, payload: AnalysisStartRequest) =>
    axiosInstance.post<AnalysisStartResponse>(
      `/projects/${projectId}/analysis/start`,
      payload,
    ),
  runAnalysis: (projectId: string, analysisId: string) =>
    axiosInstance.post<AnalysisRunResponse>(
      `/projects/${projectId}/analysis/${analysisId}/run`,
    ),
  runAnalysisStream: (
    projectId: string,
    analysisId: string,
    onProgress?: (stage: string, message: string) => void,
    conversationId?: string | null,
  ) => runAnalysisStream(projectId, analysisId, onProgress, conversationId),
  listConversations: (projectId: string) =>
    axiosInstance.get<PlaygroundConversation[]>(
      `/projects/${projectId}/conversations`,
    ),
  getConversation: (projectId: string, conversationId: string) =>
    axiosInstance.get<PlaygroundConversationDetail>(
      `/projects/${projectId}/conversations/${conversationId}`,
    ),
  deleteConversation: (projectId: string, conversationId: string) =>
    axiosInstance.delete<void>(
      `/projects/${projectId}/conversations/${conversationId}`,
    ),
  submitFeedback: (
    projectId: string,
    attemptId: string,
    feedback: 'correct' | 'incorrect',
  ) =>
    axiosInstance.patch<void>(
      `/projects/${projectId}/attempts/${attemptId}/feedback`,
      { feedback },
    ),
  confirmFeedback: (
    projectId: string,
    attemptId: string,
    payload: { confirmed_sql: string; rule_text: string },
  ) =>
    axiosInstance.post<void>(
      `/projects/${projectId}/attempts/${attemptId}/confirm`,
      payload,
    ),
};

export default projectsApi;
