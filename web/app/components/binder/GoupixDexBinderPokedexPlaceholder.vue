<template>
  <div
    class="pointer-events-none absolute inset-0 flex items-center justify-center overflow-hidden rounded-md bg-white"
  >
    <img
      :src="placeholder.artworkUrl"
      :alt="placeholder.pokemonName"
      class="max-h-[74%] max-w-[86%] object-contain"
      loading="lazy"
      decoding="async"
    />
    <div class="absolute inset-x-0 bottom-0 flex items-end justify-between gap-1 px-1.5 pb-1">
      <span class="truncate text-[9px] leading-tight font-semibold text-neutral-700">{{
        placeholder.pokemonName
      }}</span>
      <span class="num shrink-0 text-[9px] font-semibold text-neutral-400">{{ dexLabel }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { PokedexPlaceholder } from '~/utils/pokedex/kanto'

const props = defineProps<{
  placeholder: PokedexPlaceholder
}>()

const dexLabel = computed(() => `#${String(props.placeholder.dexNumber).padStart(3, '0')}`)
</script>
