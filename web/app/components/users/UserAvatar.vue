<script setup lang="ts">
const props = defineProps<{
  userId: number
  size?: 'sm' | 'md' | 'lg'
}>()

const SIZE_CLASS: Record<NonNullable<typeof props.size>, string> = {
  sm: 'size-8',
  md: 'size-10',
  lg: 'size-12'
}

const sizeClass = computed(() => SIZE_CLASS[props.size ?? 'md'])

/** Cycle the PokéAPI ID 1..898 (national dex) so we never request a 404 sprite. */
const spriteId = computed(() => ((props.userId - 1) % 898) + 1)
const src = computed(
  () => `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/shiny/${spriteId.value}.png`
)
const errored = ref(false)
</script>

<template>
  <span
    class="relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-elevated/60 ring-1 ring-default"
    :class="sizeClass"
  >
    <img
      v-if="!errored"
      :src="src"
      :alt="`Avatar utilisateur #${userId}`"
      class="h-full w-full object-contain scale-[1.6]"
      loading="lazy"
      decoding="async"
      @error="errored = true"
    >
    <UIcon
      v-else
      name="i-lucide-user"
      class="text-muted size-1/2"
    />
  </span>
</template>
