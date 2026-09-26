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
import type { ComputedRef, PropType, Ref } from 'vue'
import type { CatalogLocale } from '~/composables/useCardCatalog'
import type { GoupixDexCatalogSetLogoProps } from '~/types/GoupixDexCatalogSetLogo'
import { catalogLogoCandidates } from '~/utils/catalogAssets'
import { setLogoOverride } from '~/utils/catalog/setLogoOverrides'

const props: GoupixDexCatalogSetLogoProps = defineProps({
  logo: {
    type: String,
    default: undefined,
  },
  symbol: {
    type: String,
    default: undefined,
  },
  cover: {
    type: String,
    default: undefined,
  },
  fallbackImage: {
    type: String,
    default: undefined,
  },
  name: {
    type: String,
    required: true,
  },
  large: {
    type: Boolean,
    default: false,
  },
  setId: {
    type: String,
    default: undefined,
  },
  locale: {
    type: String as PropType<CatalogLocale>,
    default: 'fr',
  },
})

const candidateIndex: Ref<number> = ref(0)

const candidates: ComputedRef<string[]> = computed((): string[] => {
  const override: string | null = setLogoOverride(props.setId, props.locale ?? 'fr')
  const base: string[] = catalogLogoCandidates(props.logo, props.symbol, props.cover)
  const logoUrls: string[] = override ? [override, ...base] : base
  return props.fallbackImage ? [...logoUrls, props.fallbackImage] : logoUrls
})

const currentSrc: ComputedRef<string | undefined> = computed(
  (): string | undefined => candidates.value[candidateIndex.value],
)

const imgClass: ComputedRef<string> = computed((): string => {
  const isCover: boolean =
    (Boolean(props.cover) && currentSrc.value === props.cover) ||
    (Boolean(props.fallbackImage) && currentSrc.value === props.fallbackImage)
  if (isCover) {
    return 'mx-auto h-14 rounded-md object-contain shadow-sm'
  }
  return props.large ? 'mx-auto h-14 max-w-full object-contain' : 'mx-auto h-12 max-w-full object-contain'
})

watch(
  (): (string | undefined)[] => [props.logo, props.symbol, props.cover, props.fallbackImage, props.setId, props.locale],
  (): void => {
    candidateIndex.value = 0
  },
)

/**
 * Passe au logo candidat suivant quand l'image courante ne se charge pas.
 * @returns {void}
 */
function onError(): void {
  if (candidateIndex.value < candidates.value.length - 1) {
    candidateIndex.value += 1
  } else {
    candidateIndex.value = candidates.value.length
  }
}
</script>
