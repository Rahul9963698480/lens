import { useQueryClient } from '@tanstack/react-query'

import { useApiMutation, useApiQuery } from '@/hooks/use-api'
import { projectsApi } from '@/lib/api'
import type {
  ColumnAnnotationPayload,
  CreateProjectPayload,
  Project,
  ProjectPreviewResponse,
  ProjectSchemaResponse,
  TableAnnotationPayload,
  TableSchema,
} from '@/types/project'

export const projectKeys = {
  all: ['projects'] as const,
  schema: (projectId: string) =>
    [...projectKeys.all, projectId, 'schema'] as const,
  preview: (projectId: string) =>
    [...projectKeys.all, projectId, 'preview'] as const,
}

export function useProjects() {
  return useApiQuery<Project[]>(projectKeys.all, () => projectsApi.list())
}

export function useProjectSchema(projectId: string | undefined) {
  return useApiQuery<ProjectSchemaResponse>(
    projectKeys.schema(projectId ?? ''),
    () => projectsApi.getSchema(projectId!),
    { enabled: Boolean(projectId) },
  )
}

export function useProjectPreview(projectId: string | undefined) {
  return useApiQuery<ProjectPreviewResponse>(
    projectKeys.preview(projectId ?? ''),
    () => projectsApi.getPreview(projectId!),
    { enabled: Boolean(projectId) },
  )
}

type UseCreateProjectOptions = {
  onSuccess?: () => void
  onError?: (error: unknown) => void
}

export function useCreateProject(options?: UseCreateProjectOptions) {
  const queryClient = useQueryClient()

  return useApiMutation<CreateProjectPayload, Project>(
    (payload) => projectsApi.create(payload),
    {
      successMessage: 'Project created',
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: projectKeys.all })
        options?.onSuccess?.()
      },
      onError: (error) => {
        options?.onError?.(error)
      },
    },
  )
}


type UpdateTableAnnotationsVariables = {
  projectId: string
  tableName: string
  payload: TableAnnotationPayload
}

export function useUpdateTableAnnotations(projectId: string | undefined) {
  const queryClient = useQueryClient()

  return useApiMutation<UpdateTableAnnotationsVariables, TableSchema>(
    ({ projectId: id, tableName, payload }) =>
      projectsApi.updateTableAnnotations(id, tableName, payload),
    {
      successMessage: false,
      onSuccess: () => {
        if (projectId) {
          queryClient.invalidateQueries({ queryKey: projectKeys.schema(projectId) })
        }
      },
    },
  )
}

type UpdateColumnAnnotationsVariables = {
  projectId: string
  tableName: string
  columnName: string
  payload: ColumnAnnotationPayload
}

export function useUpdateColumnAnnotations(projectId: string | undefined) {
  const queryClient = useQueryClient()

  return useApiMutation<UpdateColumnAnnotationsVariables, TableSchema>(
    ({ projectId: id, tableName, columnName, payload }) =>
      projectsApi.updateColumnAnnotations(id, tableName, columnName, payload),
    {
      successMessage: false,
      onSuccess: () => {
        if (projectId) {
          queryClient.invalidateQueries({ queryKey: projectKeys.schema(projectId) })
        }
      },
    },
  )
}
