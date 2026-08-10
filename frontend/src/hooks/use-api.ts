import {
  useMutation,
  useQuery,
  type UseMutationOptions,
  type UseQueryOptions,
} from '@tanstack/react-query'

import { notify } from '@/lib/notify'

export function useApiQuery<TData>(
  key: readonly unknown[],
  queryFn: () => Promise<TData>,
  options?: Omit<UseQueryOptions<TData>, 'queryKey' | 'queryFn'>,
) {
  return useQuery<TData>({
    queryKey: key,
    queryFn,
    ...options,
  })
}

type UseApiMutationOptions<TResponse, TPayload> = UseMutationOptions<
  TResponse,
  unknown,
  TPayload
> & {
  successMessage?: string | false
}

export function useApiMutation<TPayload, TResponse>(
  mutationFn: (payload: TPayload) => Promise<TResponse>,
  options?: UseApiMutationOptions<TResponse, TPayload>,
) {
  const { successMessage, ...mutationOptions } = options ?? {}

  return useMutation<TResponse, unknown, TPayload>({
    ...mutationOptions,
    mutationFn,
    onSuccess: (data, variables, context) => {
      if (successMessage !== false) {
        notify.success({ title: successMessage ?? 'Operation successful' })
      }
      mutationOptions.onSuccess?.(data, variables, context, undefined as any)
    },
  })
}
