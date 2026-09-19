<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-[100] flex items-center justify-center p-4 backdrop-blur-sm"
      :style="{ backgroundColor: 'var(--app-overlay)' }"
      @click.self="onBackdrop"
    >
      <div
        ref="panelRef"
        class="app-card mx-auto w-full p-6 shadow-(--app-shadow-soft)"
        :class="widthClass"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="titleId"
        @keydown.escape="onEscape"
      >
        <div class="mb-5 flex items-start justify-between gap-4">
          <div class="min-w-0 flex-1">
            <h2 :id="titleId" class="font-display text-base font-semibold text-(--app-ink)">{{ title }}</h2>
            <p v-if="description" class="text-muted mt-1 text-sm leading-relaxed">{{ description }}</p>
          </div>
          <button
            type="button"
            class="text-muted shrink-0 p-1 transition-colors hover:text-(--app-ink)"
            aria-label="Fermer"
            @click="close"
          >
            <UIcon name="i-lucide-x" class="size-4" />
          </button>
        </div>

        <slot />

        <div v-if="$slots.footer" class="mt-6 flex gap-3">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    title: string
    description?: string
    widthClass?: string
    closeOnBackdrop?: boolean
  }>(),
  {
    description: undefined,
    widthClass: 'max-w-md',
    closeOnBackdrop: true,
  },
)

const open = defineModel<boolean>('open', { default: false })

const emit = defineEmits<{
  close: []
}>()

const titleId = useId()
const panelRef = ref<HTMLElement | null>(null)

function close(): void {
  open.value = false
  emit('close')
}

function onBackdrop(): void {
  if (props.closeOnBackdrop) {
    close()
  }
}

function onEscape(): void {
  close()
}

watch(open, (isOpen) => {
  if (!import.meta.client) {
    return
  }
  document.body.style.overflow = isOpen ? 'hidden' : ''
  if (isOpen) {
    nextTick(() => {
      const focusable = panelRef.value?.querySelector<HTMLElement>(
        'input:not([disabled]), textarea:not([disabled]), select:not([disabled])',
      )
      focusable?.focus()
    })
  }
})

onBeforeUnmount(() => {
  if (import.meta.client) {
    document.body.style.overflow = ''
  }
})
</script>
