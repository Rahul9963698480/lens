import type {
  ColumnAnnotationPayload,
  CreateProjectPayload,
  Project,
  ProjectPreviewResponse,
  ProjectSchemaResponse,
  TableAnnotationPayload,
  TableSchema,
} from '@/types/project'
import type {
  SqlExecuteRequest,
  SqlExecuteResponse,
  SqlGenerateRequest,
  SqlGenerateResponse,
} from '@/types/sql'

import axiosInstance from './axios-instance'

const projectsApi = {
  list: () => axiosInstance.get<Project[]>('/projects'),
  create: (payload: CreateProjectPayload) =>
    axiosInstance.post<Project>('/projects', payload),
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
  generateSql: (projectId: string, payload: SqlGenerateRequest) =>
    axiosInstance.post<SqlGenerateResponse>(
      `/projects/${projectId}/sql/generate`,
      payload,
    ),
  executeSql: (projectId: string, payload: SqlExecuteRequest) =>
    axiosInstance.post<SqlExecuteResponse>(
      `/projects/${projectId}/sql/execute`,
      payload,
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
