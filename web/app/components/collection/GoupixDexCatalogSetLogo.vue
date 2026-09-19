<template>
  <img
    v-if="currentSrc"
    :src="currentSrc"
    :alt="name"
    loading="lazy"
    decoding="async"
    referrerpolicy="no-referrer"
    :class="imgClass"
    @error="onError"
  />
  <UIcon v-else name="i-lucide-layers" class="text-muted size-7" aria-hidden />
</template>

<script setup lang="ts">
import { catalogLogoCandidates } from '~/utils/catalogAssets'

const props = defineProps<{
  logo?: string
  symbol?: string
  cover?: string
  name: string
  large?: boolean
}>()

const idx = ref(0)

const candidates = computed(() => catalogLogoCandidates(props.logo, props.symbol, props.cover))

const currentSrc = computed(() => candidates.value[idx.value])

const imgClass = computed(() => {
  const isCover = props.cover && currentSrc.value === props.cover
  if (isCover) {
    return 'mx-auto h-14 rounded-md object-contain shadow-sm'
  }
  return props.large ? 'mx-auto h-14 max-w-full object-contain' : 'mx-auto h-12 max-w-full object-contain'
})

watch(
  () => [props.logo, props.symbol, props.cover],
  () => {
    idx.value = 0
  },
)

function onError(): void {
  if (idx.value < candidates.value.length - 1) {
    idx.value += 1
  } else {
    idx.value = candidates.value.length
  }
}
</script>
