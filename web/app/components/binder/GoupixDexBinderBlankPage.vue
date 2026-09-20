<template>
  <section
    aria-label="Feuille vierge"
    :style="{ width: `${size.w}px`, height: `${size.h}px` }"
    class="relative z-0 shrink-0 overflow-hidden rounded-l-xl border-y border-l shadow-(--app-shadow-soft)"
    :class="[sheet.page, turnClass]"
  >
    <span
      aria-hidden
      class="pointer-events-none absolute inset-y-0 right-0 w-12 rounded-r-[inherit] bg-gradient-to-l to-transparent"
      :class="sheet.gutter"
    />
    <GoupixDexBinderHoles side="right" :positions="ringPos" :cls="sheet.holes" />
    <button
      type="button"
      class="group/edge absolute inset-y-0 left-0 z-10 flex w-7 cursor-pointer items-center justify-center rounded-l-[inherit] text-(--app-faint) transition hover:bg-gradient-to-r hover:from-black/25 hover:to-transparent hover:text-(--app-ink)"
      aria-label="Fermer le classeur"
      @click="$emit('edge-prev')"
    >
      <UIcon name="i-lucide-chevron-left" class="opacity-40 group-hover/edge:opacity-100" />
    </button>
  </section>
</template>

<script setup lang="ts">
import type { PageSize } from '~/composables/useBinderPages'

defineProps<{
  size: PageSize
  sheet: { page: string; gutter: string; holes: string }
  ringPos: number[]
  turnClass: string
}>()

defineEmits<{ 'edge-prev': [] }>()
</script>
