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
import axiosInstance from './axios-instance'

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
