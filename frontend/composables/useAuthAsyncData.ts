import type { AsyncDataOptions, AsyncData } from 'nuxt/app'
import type { NuxtError } from '#app'

/**
 * useAsyncData for authenticated pages.
 * Tokens live in localStorage, so fetches must run on the client only
 * and must not reuse an empty SSR/hydration payload.
 */
export function useAuthAsyncData<DataT>(
  key: string,
  handler: () => Promise<DataT>,
  options: AsyncDataOptions<DataT> = {}
): AsyncData<DataT | null, NuxtError | null> {
  return useAsyncData(key, handler, {
    server: false,
    getCachedData: () => undefined,
    ...options
  }) as AsyncData<DataT | null, NuxtError | null>
}
