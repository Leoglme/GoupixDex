<template>
  <img
    v-if="realSrc"
    :src="realSrc"
    :alt="alt"
    class="h-full w-full object-cover"
    loading="lazy"
    decoding="async"
    @error="onError"
  />
  <img
    v-else-if="fallbackSrc"
    :src="fallbackSrc"
    :alt="alt"
    class="h-full w-full scale-90 object-contain opacity-90"
    loading="lazy"
    decoding="async"
  />
  <div v-else class="flex h-full w-full items-center justify-center bg-(--app-surface-2) text-xs text-(--app-faint)">
    —
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  src: string | null | undefined
  alt?: string
  /** Artwork de repli (ex. Pokédex) affiché si `src` est absent ou en erreur. */
  fallbackSrc?: string | null
}>()

const errored = ref(false)

watch(
  () => props.src,
  () => {
    errored.value = false
  },
)

const realSrc = computed(() => (props.src && !errored.value ? props.src : null))

function onError(): void {
  errored.value = true
}
</script>
