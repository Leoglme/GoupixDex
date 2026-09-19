<template>
  <div
    v-if="positionLabel"
    class="flex items-center justify-between gap-3 border-b border-[var(--app-line-soft)] px-4 py-2.5 sm:px-5"
  >
    <UButton
      color="neutral"
      variant="subtle"
      size="xs"
      icon="i-lucide-chevron-left"
      :disabled="!canPrevious"
      @click="emit('previous')"
    >
      Précédent
    </UButton>
    <span class="text-[11px] whitespace-nowrap text-[var(--app-ink-soft)] tabular-nums">
      {{ positionLabel }}
    </span>
    <UButton
      color="neutral"
      variant="subtle"
      size="xs"
      trailing-icon="i-lucide-chevron-right"
      :disabled="!canNext"
      @click="emit('next')"
    >
      Suivant
    </UButton>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    positionLabel?: string
    canPrevious?: boolean
    canNext?: boolean
  }>(),
  {
    positionLabel: '',
    canPrevious: false,
    canNext: false,
  },
)

const emit = defineEmits<{
  previous: []
  next: []
}>()
</script>
