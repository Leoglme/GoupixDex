<template>
  <div class="flex flex-wrap items-center gap-2" role="group" :aria-label="label">
    <button
      v-if="withNeutral"
      type="button"
      title="Neutre"
      :aria-pressed="modelValue == null"
      class="flex h-7 w-7 items-center justify-center rounded-full border bg-(--app-surface-2) text-[10px] text-(--app-faint) transition"
      :class="
        modelValue == null
          ? 'border-(--app-accent) ring-2 ring-(--app-accent-soft)'
          : 'border-(--app-line) hover:scale-110'
      "
      @click="$emit('update:modelValue', null)"
    >
      ∅
    </button>
    <button
      v-for="c in colors"
      :key="c"
      type="button"
      :title="c"
      :aria-pressed="modelValue === c"
      class="h-7 w-7 rounded-full border transition hover:scale-110"
      :class="modelValue === c ? 'border-(--app-ink) ring-2 ring-(--app-accent-soft)' : 'border-black/20'"
      :style="{ backgroundColor: c }"
      @click="$emit('update:modelValue', c)"
    />
    <label
      class="relative h-7 w-7 cursor-pointer overflow-hidden rounded-full border border-(--app-line) bg-[conic-gradient(red,yellow,lime,cyan,blue,magenta,red)]"
      title="Autre couleur"
    >
      <input
        type="color"
        class="absolute inset-0 cursor-pointer opacity-0"
        :value="modelValue ?? '#ffffff'"
        aria-label="Autre couleur"
        @input="onPick(($event.target as HTMLInputElement).value)"
      />
    </label>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string
    colors: readonly string[]
    modelValue: string | null
    withNeutral?: boolean
  }>(),
  { withNeutral: false },
)

const emit = defineEmits<{ 'update:modelValue': [string | null] }>()

function onPick(hex: string): void {
  emit('update:modelValue', hex)
}
</script>
