<template>
  <Teleport to="body">
    <div class="pointer-events-none fixed right-4 bottom-4 z-[110] flex w-[min(22rem,calc(100vw-2rem))] flex-col gap-2">
      <TransitionGroup name="goupix-toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="pointer-events-auto flex items-start gap-3 rounded-xl border border-(--app-line) bg-(--app-surface) p-3.5 shadow-lg shadow-black/10"
        >
          <span
            class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full"
            :style="{ backgroundColor: tone(toast.type).tileBg }"
          >
            <UIcon :name="tone(toast.type).icon" class="h-4 w-4" :style="{ color: tone(toast.type).iconColor }" />
          </span>
          <div class="min-w-0 flex-1 pt-0.5">
            <p class="text-sm leading-snug font-medium text-(--app-ink)">{{ toast.title }}</p>
            <p v-if="toast.description" class="text-muted mt-0.5 text-xs leading-snug">{{ toast.description }}</p>
          </div>
          <button
            type="button"
            class="flex h-6 w-6 shrink-0 cursor-pointer items-center justify-center rounded text-(--app-faint) transition-colors hover:bg-(--app-surface-2) hover:text-(--app-ink)"
            aria-label="Fermer la notification"
            @click="dismiss(toast.id)"
          >
            <UIcon name="i-lucide-x" class="h-3.5 w-3.5" />
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import type { ToastItem, ToastType } from '~/composables/useToast'
import { useToastHost } from '~/composables/useToast'

type Tone = { icon: string; tileBg: string; iconColor: string }

const TONE: Record<ToastType, Tone> = {
  success: { icon: 'i-lucide-check', tileBg: 'var(--app-green-soft)', iconColor: 'var(--app-green)' },
  error: { icon: 'i-lucide-circle-alert', tileBg: 'var(--app-red-soft)', iconColor: 'var(--app-red)' },
  warning: { icon: 'i-lucide-triangle-alert', tileBg: 'var(--app-accent-soft)', iconColor: 'var(--app-accent-ink)' },
  info: { icon: 'i-lucide-info', tileBg: 'var(--app-blue-soft)', iconColor: 'var(--app-blue)' },
}

function tone(type: ToastType): Tone {
  return TONE[type]
}

const { toasts, dismiss } = useToastHost()

const scheduled = new Set<number>()

watch(
  toasts,
  (items: ToastItem[]) => {
    for (const item of items) {
      if (scheduled.has(item.id)) continue
      scheduled.add(item.id)
      setTimeout(() => {
        dismiss(item.id)
        scheduled.delete(item.id)
      }, item.duration)
    }
  },
  { deep: true },
)
</script>

<style scoped>
.goupix-toast-enter-active,
.goupix-toast-leave-active {
  transition:
    transform 0.22s cubic-bezier(0.4, 0, 0.2, 1),
    opacity 0.22s ease;
}
.goupix-toast-enter-from {
  transform: translateY(8px);
  opacity: 0;
}
.goupix-toast-leave-to {
  transform: translateX(12px);
  opacity: 0;
}
.goupix-toast-move {
  transition: transform 0.22s cubic-bezier(0.4, 0, 0.2, 1);
}
</style>
