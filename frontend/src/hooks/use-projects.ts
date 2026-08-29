import { useQueryClient } from '@tanstack/react-query'

import { useApiMutation, useApiQuery } from '@/hooks/use-api'
import { projectsApi } from '@/lib/api'
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
  AnalysisStartResponse,
} from '@/types/analysis'
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
  onError?: () => void
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
      onError: () => {
        options?.onError?.()
      },
    },
  )
}

export function useUploadXlsxProject(options?: UseCreateProjectOptions) {
  const queryClient = useQueryClient()

  return useApiMutation<CreateXlsxProjectPayload, Project>(
    (payload) => projectsApi.uploadXlsx(payload),
    {
      successMessage: 'Project created',
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: projectKeys.all })
        options?.onSuccess?.()
      },
      onError: () => {
        options?.onError?.()
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

type StartAnalysisVariables = {
  projectId: string
  question: string
}

export function useStartAnalysis() {
  return useApiMutation<StartAnalysisVariables, AnalysisStartResponse>(
    ({ projectId, question }) => projectsApi.startAnalysis(projectId, { question }),
    { successMessage: false },
  )
}

type RunAnalysisVariables = {
  projectId: string
  analysisId: string
  onProgress?: (stage: string, message: string) => void
}

export function useRunAnalysis() {
  return useApiMutation<RunAnalysisVariables, AnalysisRunResponse>(
    ({ projectId, analysisId, onProgress }) =>
      projectsApi.runAnalysisStream(projectId, analysisId, onProgress),
    { successMessage: false },
  )
}

type SubmitFeedbackVariables = {
  projectId: string
  attemptId: string
  feedback: 'correct' | 'incorrect'
}

export function useSubmitFeedback() {
  return useApiMutation<SubmitFeedbackVariables, void>(
    ({ projectId, attemptId, feedback }) =>
      projectsApi.submitFeedback(projectId, attemptId, feedback),
    { successMessage: false },
  )
}

type ConfirmFeedbackVariables = {
  projectId: string
  attemptId: string
  confirmed_sql: string
  rule_text: string
}

export function useConfirmFeedback() {
  return useApiMutation<ConfirmFeedbackVariables, void>(
    ({ projectId, attemptId, confirmed_sql, rule_text }) =>
      projectsApi.confirmFeedback(projectId, attemptId, { confirmed_sql, rule_text }),
    { successMessage: 'Feedback confirmed' },
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
