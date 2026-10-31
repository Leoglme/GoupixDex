<template>
  <Teleport to="body">
    <div
      class="pointer-events-none fixed inset-x-0 top-0 z-[350] flex flex-col items-center gap-2 px-3 pt-[max(0.75rem,env(safe-area-inset-top))]"
      role="region"
      aria-label="Notifications"
    >
      <TransitionGroup
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="-translate-y-3 opacity-0"
        leave-active-class="transition duration-150 ease-in"
        leave-to-class="-translate-y-3 opacity-0"
        move-class="transition duration-200 ease-out"
      >
        <div
          v-for="toast in displayedToasts"
          :key="toast.id"
          role="status"
          class="pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-2xl border border-(--app-line) bg-(--app-surface)/95 p-3 shadow-lg shadow-black/10 backdrop-blur-xl"
        >
          <span
            class="flex size-8 shrink-0 items-center justify-center rounded-full"
            :class="TOAST_TONE_STYLES[resolveToastTone(toast)].iconTileClass"
          >
            <UIcon :name="toast.icon || TOAST_TONE_STYLES[resolveToastTone(toast)].icon" class="size-4" />
          </span>
          <div class="min-w-0 flex-1 pt-1">
            <p class="text-sm leading-snug font-semibold text-(--app-ink)">{{ toast.title }}</p>
            <p v-if="toast.description" class="mt-0.5 text-sm leading-snug text-(--app-ink-soft)">
              {{ toast.description }}
            </p>
            <div v-if="toast.actions?.length" class="mt-2 flex flex-wrap gap-1.5">
              <UButton
                v-for="(action, actionIndex) in toast.actions"
                :key="actionIndex"
                size="xs"
                v-bind="action"
                @click="remove(toast.id)"
              />
            </div>
          </div>
          <button
            type="button"
            class="-mt-0.5 -mr-0.5 flex size-7 shrink-0 cursor-pointer items-center justify-center rounded-full text-(--app-faint) transition-colors hover:bg-(--app-surface-2) hover:text-(--app-ink)"
            aria-label="Fermer la notification"
            @click="remove(toast.id)"
          >
            <UIcon name="i-lucide-x" class="size-4" />
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script lang="ts" setup>
import type { Toast } from '@nuxt/ui/composables'
import type { ComputedRef } from 'vue'
import type { ToastTone, ToastToneStyle } from '~/types/GoupixDexToastHost'

const { toasts, remove } = useToast()

const TOAST_TONE_STYLES: Record<ToastTone, ToastToneStyle> = {
  success: { icon: 'i-lucide-check', iconTileClass: 'bg-(--app-green-soft) text-(--app-green)' },
  error: { icon: 'i-lucide-circle-alert', iconTileClass: 'bg-(--app-red-soft) text-(--app-red)' },
  warning: { icon: 'i-lucide-triangle-alert', iconTileClass: 'bg-(--app-accent-soft) text-(--app-accent-ink)' },
  info: { icon: 'i-lucide-info', iconTileClass: 'bg-(--app-blue-soft) text-(--app-blue)' },
}
const ERROR_TOAST_DURATION_MS: number = 5_000
const OTHER_TOAST_DURATION_MS: number = 3_500
const handledToastIds: Set<Toast['id']> = new Set()
const closingTimerByToastId: Map<Toast['id'], ReturnType<typeof setTimeout>> = new Map()

const displayedToasts: ComputedRef<Toast[]> = computed((): Toast[] =>
  toasts.value.filter((toast: Toast): boolean => toast.open !== false).reverse(),
)

/**
 * Famille visuelle d'un toast d'après sa couleur : succès, erreur, avertissement, sinon information.
 * @param {Toast} toast - Toast à afficher.
 * @returns {ToastTone} Famille qui choisit l'icône et sa teinte.
 */
function resolveToastTone(toast: Toast): ToastTone {
  if (toast.color === 'success' || toast.color === 'error' || toast.color === 'warning') {
    return toast.color
  }
  return 'info'
}

/**
 * Ferme le toast après sa durée, et retire le succès précédent quand un nouveau succès arrive.
 * @param {Toast} toast - Toast qui vient d'apparaître.
 * @returns {void}
 */
function scheduleToastClosing(toast: Toast): void {
  if (resolveToastTone(toast) === 'success') {
    for (const shownToast of displayedToasts.value) {
      if (shownToast.id !== toast.id && resolveToastTone(shownToast) === 'success') {
        remove(shownToast.id)
      }
    }
  }
  const duration: number =
    toast.duration ?? (resolveToastTone(toast) === 'error' ? ERROR_TOAST_DURATION_MS : OTHER_TOAST_DURATION_MS)
  if (!Number.isFinite(duration)) {
    return
  }
  closingTimerByToastId.set(
    toast.id,
    setTimeout((): void => {
      closingTimerByToastId.delete(toast.id)
      remove(toast.id)
    }, duration),
  )
}

watch(
  displayedToasts,
  (shownToasts: Toast[]): void => {
    for (const toast of shownToasts) {
      if (!handledToastIds.has(toast.id)) {
        handledToastIds.add(toast.id)
        scheduleToastClosing(toast)
      }
    }
    for (const handledToastId of handledToastIds) {
      if (!toasts.value.some((toast: Toast): boolean => toast.id === handledToastId)) {
        handledToastIds.delete(handledToastId)
      }
    }
  },
  { immediate: true },
)

onBeforeUnmount((): void => {
  for (const closingTimer of closingTimerByToastId.values()) {
    clearTimeout(closingTimer)
  }
  closingTimerByToastId.clear()
})
</script>
