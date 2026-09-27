import type { ComputedRef, Ref } from 'vue'

export type PullToRefresh = {
  pullDistance: Ref<number>
  pullProgress: ComputedRef<number>
  isPulling: Ref<boolean>
  isRefreshing: Ref<boolean>
  hasReachedRefreshThreshold: ComputedRef<boolean>
}
