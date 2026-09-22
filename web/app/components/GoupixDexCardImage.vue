<template>
  <img
    v-if="currentSrc"
    :src="currentSrc"
    :alt="alt"
    :class="imgClass"
    referrerpolicy="no-referrer"
    loading="lazy"
    decoding="async"
    @error="onError"
  />
  <div v-else class="flex h-full w-full items-center justify-center">
    <UIcon name="i-lucide-image-off" class="text-muted size-8" />
  </div>
</template>

<script setup lang="ts">
import { limitlessCardImageUrl } from '~/utils/cards/limitlessCardImage'

/**
 * Image d'une carte Pokémon avec repli : `image_url` TCGdex, sinon l'image LimitlessTCG
 * (cartes japonaises récentes absentes de TCGdex), sinon une icône « image manquante ».
 */
const props = withDefaults(
  defineProps<{
    imageUrl?: string | null
    tcgdexCardId?: string | null
    alt?: string
    imgClass?: string
  }>(),
  {
    imageUrl: null,
    tcgdexCardId: null,
    alt: '',
    imgClass: 'h-full w-full object-contain',
  },
)

const failedSrcs = ref<Set<string>>(new Set())

const candidates = computed<string[]>(() => {
  const list: string[] = []
  const primary = (props.imageUrl ?? '').trim()
  if (primary) {
    list.push(primary)
  }
  const fallback = limitlessCardImageUrl(props.tcgdexCardId)
  if (fallback && !list.includes(fallback)) {
    list.push(fallback)
  }
  return list
})

const currentSrc = computed<string | null>(() => candidates.value.find((src) => !failedSrcs.value.has(src)) ?? null)

watch(candidates, () => {
  failedSrcs.value = new Set()
})

/**
 * Marque la source courante comme en échec pour tenter le repli suivant.
 * @returns {void}
 */
function onError(): void {
  const src = currentSrc.value
  if (src) {
    failedSrcs.value = new Set([...failedSrcs.value, src])
  }
}
</script>
