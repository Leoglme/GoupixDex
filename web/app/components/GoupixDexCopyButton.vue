<template>
  <UButton
    type="button"
    color="neutral"
    variant="outline"
    :icon="copyState === 'copied' ? 'i-lucide-check' : 'i-lucide-copy'"
    :ui="{ leadingIcon: copyState === 'copied' ? 'text-(--app-green)' : undefined }"
    @click="copyValue"
  >
    <span aria-live="polite">{{ buttonLabel }}</span>
  </UButton>
</template>

<script lang="ts" setup>
import type { ComputedRef, Ref } from 'vue'
import type { CopyFeedbackState, GoupixDexCopyButtonProps } from '~/types/GoupixDexCopyButton'

const props: GoupixDexCopyButtonProps = defineProps({
  value: {
    type: String,
    required: true,
  },
  label: {
    type: String,
    required: true,
  },
})

const COPY_FEEDBACK_DURATION_MS: number = 1800
let feedbackTimer: ReturnType<typeof setTimeout> | undefined

const copyState: Ref<CopyFeedbackState> = ref('idle')

const buttonLabel: ComputedRef<string> = computed((): string => {
  if (copyState.value === 'copied') return 'Copié'
  if (copyState.value === 'failed') return 'Copie impossible'
  return props.label
})

/**
 * Copie la valeur dans le presse-papiers, puis affiche le résultat le temps du retour visuel.
 * @returns {Promise<void>} Résolue une fois la copie tentée.
 */
async function copyValue(): Promise<void> {
  try {
    await navigator.clipboard.writeText(props.value)
    copyState.value = 'copied'
  } catch {
    copyState.value = 'failed'
  }
  clearTimeout(feedbackTimer)
  feedbackTimer = setTimeout((): void => {
    copyState.value = 'idle'
  }, COPY_FEEDBACK_DURATION_MS)
}

onBeforeUnmount((): void => {
  clearTimeout(feedbackTimer)
})
</script>
