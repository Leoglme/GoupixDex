<template>
  <div
    :class="[
      'border-default/45 flex gap-4 rounded-2xl border p-4 shadow-sm sm:gap-5 sm:p-5',
      'from-elevated/90 to-elevated/45 bg-gradient-to-br ring-1 ring-white/10 ring-inset dark:ring-white/5',
      tone.root,
    ]"
    role="alert"
  >
    <div
      :class="['flex size-11 shrink-0 items-center justify-center rounded-xl ring-1 ring-inset sm:size-12', tone.chip]"
      aria-hidden="true"
    >
      <UIcon :name="resolvedIcon" :class="['size-5 sm:size-[1.35rem]', iconClass]" />
    </div>

    <div class="min-w-0 flex-1 space-y-2">
      <p class="text-highlighted text-sm font-semibold tracking-tight sm:text-base">
        {{ title }}
      </p>
      <div v-if="$slots.default || description" class="text-muted text-sm leading-relaxed">
        <slot>{{ description }}</slot>
      </div>
      <div v-if="$slots.actions" class="flex flex-wrap items-center gap-2 pt-0.5">
        <slot name="actions" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { PropType } from 'vue'
import type { GoupixDexAlertProps, GoupixDexAlertVariant } from '~/types/GoupixDexAlert'

const props: GoupixDexAlertProps = defineProps({
  variant: {
    type: String as PropType<GoupixDexAlertVariant>,
    default: 'info',
  },
  title: {
    type: String,
    required: true,
  },
  description: {
    type: String,
    default: undefined,
  },
  icon: {
    type: String,
    default: undefined,
  },
  iconClass: {
    type: String,
    default: '',
  },
})

const DEFAULT_ICONS: Record<GoupixDexAlertVariant, string> = {
  warning: 'i-lucide-alert-triangle',
  success: 'i-lucide-check-circle-2',
  error: 'i-lucide-circle-alert',
  info: 'i-lucide-info',
}

const toneClasses: Record<GoupixDexAlertVariant, { root: string; chip: string }> = {
  warning: {
    root: 'border-l-[3px] border-l-amber-500 dark:border-l-amber-400',
    chip: 'bg-amber-500/12 text-amber-700 ring-amber-500/25 dark:text-amber-300',
  },
  success: {
    root: 'border-l-[3px] border-l-emerald-500 dark:border-l-emerald-400',
    chip: 'bg-emerald-500/12 text-emerald-700 ring-emerald-500/25 dark:text-emerald-300',
  },
  error: {
    root: 'border-l-[3px] border-l-red-500 dark:border-l-red-400',
    chip: 'bg-red-500/12 text-red-700 ring-red-500/25 dark:text-red-300',
  },
  info: {
    root: 'border-l-[3px] border-l-primary',
    chip: 'bg-primary/12 text-primary ring-primary/25',
  },
}

const tone = computed(() => toneClasses[props.variant])

const resolvedIcon = computed(() => props.icon ?? DEFAULT_ICONS[props.variant])
</script>
