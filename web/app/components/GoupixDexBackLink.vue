<template>
  <NuxtLink
    :to="props.to"
    class="inline-flex w-fit items-center gap-1 text-sm font-medium text-(--app-accent) underline-offset-4 transition hover:text-(--app-accent) hover:underline"
  >
    <UIcon name="i-lucide-arrow-left" class="size-4 shrink-0" aria-hidden />
    {{ props.label }}
  </NuxtLink>
</template>

<script lang="ts" setup>
import type { GoupixDexBackLinkProps } from '~/types/GoupixDexBackLink'

/**
 * Lien de retour orange, placé au-dessus du titre de page (motif du catalogue Pokémon).
 */
const props: GoupixDexBackLinkProps = defineProps({
  to: {
    type: String,
    required: true,
  },
  label: {
    type: String,
    default: 'Retour',
  },
})
</script>
