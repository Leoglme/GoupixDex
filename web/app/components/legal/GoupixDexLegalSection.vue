<template>
  <section class="mt-10 [counter-increment:legal-section]">
    <h2 class="font-display text-highlighted flex items-baseline gap-3 text-xl font-semibold sm:text-2xl">
      <span
        class="shrink-0 font-mono text-sm font-medium text-(--app-accent) before:content-[counter(legal-section,decimal-leading-zero)]"
        aria-hidden="true"
      ></span>
      {{ props.title }}
    </h2>
    <div class="text-muted mt-3 grid gap-3 border-t border-(--app-line) pt-4 text-base leading-relaxed">
      <slot />
    </div>
  </section>
</template>

<script lang="ts" setup>
import type { GoupixDexLegalSectionProps } from '~/types/GoupixDexLegalSection'

/** Numérotée par le compteur CSS `legal-section` que GoupixDexLegalDocument remet à zéro : à placer dans ce composant. */
const props: GoupixDexLegalSectionProps = defineProps({
  title: {
    type: String,
    required: true,
  },
})
</script>
