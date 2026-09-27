<template>
  <div
    class="pointer-events-none fixed inset-x-0 top-0 z-[120] flex justify-center"
    :class="{ 'transition-transform duration-200 ease-out': !isPulling }"
    :style="{ transform: `translateY(${pullDistance - INDICATOR_HIDDEN_OFFSET_PX}px)` }"
    aria-hidden="true"
  >
    <span
      class="mt-2 flex size-10 items-center justify-center rounded-full border border-(--app-line) bg-(--app-surface) shadow-md shadow-black/10"
      :style="{ opacity: pullProgress }"
    >
      <UIcon
        :name="isRefreshing ? 'i-lucide-loader-2' : 'i-lucide-arrow-down'"
        class="size-5 text-(--app-accent) transition-transform duration-200"
        :class="{ 'animate-spin': isRefreshing, 'rotate-180': hasReachedRefreshThreshold && !isRefreshing }"
      />
    </span>
  </div>
</template>

<script lang="ts" setup>
import type { PullToRefresh } from '~/types/PullToRefresh'
import { usePullToRefresh } from '~/composables/usePullToRefresh'

const { pullDistance, pullProgress, isPulling, isRefreshing, hasReachedRefreshThreshold }: PullToRefresh =
  usePullToRefresh((): void => {
    reloadNuxtApp({ force: true })
  })

const INDICATOR_HIDDEN_OFFSET_PX: number = 48
</script>
