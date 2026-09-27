<template>
  <UCard class="border-primary/30 ring-primary/20 overflow-hidden ring-1" :ui="{ body: 'p-0 sm:p-0' }">
    <div class="flex flex-col gap-4 p-5 sm:p-6">
      <div class="flex flex-wrap items-center gap-3">
        <UIcon name="i-lucide-loader-circle" class="text-primary size-8 shrink-0 animate-spin" />
        <div class="min-w-0 flex-1 space-y-1">
          <p class="text-highlighted font-medium">{{ title }}</p>
          <p v-if="phaseHint" class="text-muted text-xs leading-snug">
            {{ phaseHint }}
          </p>
        </div>
        <UProgress :model-value="progressPercent" animation="carousel" class="h-1 w-full max-w-xs shrink-0 sm:w-56" />
      </div>
      <div
        ref="logScrollEl"
        class="border-default bg-elevated/40 max-h-56 overflow-y-auto rounded-lg border p-3 text-left font-mono text-xs leading-relaxed"
        aria-live="polite"
        role="log"
      >
        <p v-if="logLines.length === 0" class="text-muted">Connexion au flux de progression…</p>
        <p v-for="(line, idx) in logLines" v-else :key="idx" class="text-highlighted whitespace-pre-wrap">
          {{ line }}
        </p>
      </div>
    </div>
  </UCard>
</template>

<script setup lang="ts">
import { nextTick, ref, watch, type PropType } from 'vue'
import type { GoupixDexAmazonWorkerProgressProps } from '~/types/GoupixDexAmazonWorkerProgress'

const props: GoupixDexAmazonWorkerProgressProps = defineProps({
  title: {
    type: String,
    required: true,
  },
  phaseHint: {
    type: String,
    default: '',
  },
  logLines: {
    type: Array as PropType<string[]>,
    required: true,
  },
  progressPercent: {
    type: Number as PropType<number | null>,
    default: null,
  },
})

const logScrollEl = ref<HTMLElement | null>(null)

watch(
  () => props.logLines.length,
  async (): Promise<void> => {
    await nextTick()
    const el = logScrollEl.value
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  },
)
</script>
