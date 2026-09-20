<template>
  <div class="flex gap-2" :class="spread ? 'flex-nowrap' : 'flex-wrap'" role="group" :aria-label="label">
    <button
      v-for="o in options"
      :key="o.code"
      type="button"
      :aria-pressed="o.code === modelValue"
      class="rounded-lg border text-[13px] font-medium transition focus-visible:ring-2 focus-visible:ring-(--app-accent) focus-visible:outline-none"
      :class="[
        spread ? 'min-w-0 flex-1 px-2 py-2' : 'px-2.5 py-1.5 text-xs',
        o.code === modelValue
          ? 'border-(--app-accent)/50 bg-(--app-accent-soft) text-(--app-accent)'
          : 'text-muted border-(--app-line) hover:border-(--app-ink-soft) hover:text-(--app-ink)',
      ]"
      @click="$emit('update:modelValue', o.code)"
    >
      {{ o.label }}
    </button>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string
    options: readonly { code: string; label: string }[]
    modelValue: string
    /** Répartit les options sur une seule ligne (largeur égale). */
    spread?: boolean
  }>(),
  { spread: false },
)

defineEmits<{ 'update:modelValue': [string] }>()
</script>
