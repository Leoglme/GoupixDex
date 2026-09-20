<template>
  <Teleport to="body">
    <Transition name="goupix-drawer-backdrop">
      <div v-if="open" class="fixed inset-0 z-40 bg-(--app-overlay)" aria-hidden="true" @click="emit('close')" />
    </Transition>

    <Transition name="goupix-drawer-panel">
      <div
        v-if="open"
        class="goupix-drawer-panel border-default fixed top-0 right-0 z-50 flex h-dvh flex-col border-l bg-(--app-surface) pt-[env(safe-area-inset-top)] pr-[env(safe-area-inset-right)] pb-[env(safe-area-inset-bottom)] shadow-2xl"
        role="dialog"
        aria-modal="true"
      >
        <div class="border-default flex shrink-0 items-start gap-3 border-b px-5 py-4">
          <span
            v-if="icon || $slots.icon"
            class="border-default bg-elevated/40 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border"
          >
            <slot name="icon">
              <UIcon v-if="icon" :name="icon" class="text-muted size-4" />
            </slot>
          </span>

          <div class="min-w-0 flex-1">
            <h2 class="text-highlighted text-base leading-tight font-semibold">{{ title }}</h2>
            <p v-if="subtitle" class="text-muted mt-0.5 truncate text-xs">{{ subtitle }}</p>
          </div>

          <button
            type="button"
            class="text-muted hover:bg-elevated/60 hover:text-highlighted flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition-colors"
            aria-label="Fermer"
            @click="emit('close')"
          >
            <UIcon name="i-lucide-x" class="size-4" />
          </button>
        </div>

        <div class="min-h-0 flex-1 overflow-x-hidden overflow-y-auto px-5 py-4">
          <slot />
        </div>

        <div v-if="$slots.footer" class="border-default flex shrink-0 gap-2 border-t px-5 py-4">
          <slot name="footer" />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    subtitle?: string
    icon?: string
  }>(),
  {
    subtitle: undefined,
    icon: undefined,
  },
)

const emit = defineEmits<{
  close: []
}>()

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && props.open) {
    emit('close')
  }
}

watch(
  () => props.open,
  (isOpen) => {
    if (import.meta.client) {
      document.body.style.overflow = isOpen ? 'hidden' : ''
    }
  },
)

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  if (import.meta.client) {
    document.body.style.overflow = ''
  }
})
</script>

<style scoped>
.goupix-drawer-panel {
  width: min(480px, 100dvw);
  max-width: 480px;
}

.goupix-drawer-panel-enter-active,
.goupix-drawer-panel-leave-active {
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.goupix-drawer-panel-enter-from,
.goupix-drawer-panel-leave-to {
  transform: translateX(100%);
}

.goupix-drawer-backdrop-enter-active,
.goupix-drawer-backdrop-leave-active {
  transition: opacity 0.2s ease;
}
.goupix-drawer-backdrop-enter-from,
.goupix-drawer-backdrop-leave-to {
  opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
  .goupix-drawer-panel-enter-active,
  .goupix-drawer-panel-leave-active,
  .goupix-drawer-backdrop-enter-active,
  .goupix-drawer-backdrop-leave-active {
    transition: none;
  }
}
</style>
