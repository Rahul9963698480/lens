import type {
  ColumnAnnotationPayload,
  CreateProjectPayload,
  Project,
  ProjectPreviewResponse,
  ProjectSchemaResponse,
  TableAnnotationPayload,
  TableSchema,
} from '@/types/project'

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
};

export default projectsApi;
