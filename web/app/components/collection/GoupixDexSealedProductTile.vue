<template>
  <div
    role="button"
    tabindex="0"
    class="group bg-elevated/30 focus-visible:ring-primary flex h-full cursor-pointer flex-col overflow-hidden rounded-xl border text-left transition-all hover:-translate-y-0.5 hover:shadow-md focus-visible:ring-2 focus-visible:outline-none"
    :class="
      props.ownedQuantity > 0
        ? 'border-(--app-green) ring-2 ring-(--app-green)'
        : 'border-default hover:border-(--app-accent)'
    "
    @click="emit('select')"
    @keydown.enter.prevent="emit('select')"
  >
    <div class="relative aspect-square w-full overflow-hidden bg-white">
      <img
        v-if="props.imageUrl && !hasImageLoadFailed"
        :src="props.imageUrl"
        :alt="props.name"
        class="absolute inset-0 h-full w-full object-contain p-4 transition-transform duration-300 group-hover:scale-[1.03]"
        referrerpolicy="no-referrer"
        loading="lazy"
        decoding="async"
        @error="hasImageLoadFailed = true"
      />
      <div v-else class="absolute inset-0 flex items-center justify-center">
        <UIcon :name="sealedProductTypeIcon(props.productType)" class="size-8 text-neutral-400" />
      </div>
      <slot name="badges" />
      <GoupixDexTileCollectionControls
        :item-name="props.name"
        :owned-quantity="props.ownedQuantity"
        :is-addable="props.isAddable"
        :is-adding="props.isAdding"
        @add="emit('add')"
      />
    </div>
    <div class="flex min-w-0 flex-1 flex-col gap-0.5 p-3">
      <p class="text-highlighted line-clamp-2 min-h-[2.5em] text-sm leading-tight font-semibold">{{ props.name }}</p>
      <p class="text-muted truncate text-xs">{{ productTypeAndSetLabel }}</p>
      <div class="mt-auto space-y-0.5 pt-2">
        <div class="flex items-center justify-between gap-2">
          <span
            class="text-base font-bold tabular-nums"
            :class="props.priceLabel ? 'text-highlighted' : 'text-(--app-faint)'"
          >
            {{ props.priceLabel ?? '—' }}
          </span>
          <span
            v-if="props.gain?.percentLabel"
            class="shrink-0 rounded-full px-1.5 py-0.5 text-[11px] font-semibold tabular-nums"
            :class="GAIN_BADGE_CLASSES[props.gain.direction]"
            title="Plus-value sur le prix d'achat"
          >
            {{ props.gain.percentLabel }}
          </span>
        </div>
        <div v-if="props.purchaseLabel" class="flex items-baseline justify-between gap-2 text-xs tabular-nums">
          <span class="text-muted truncate">{{ props.purchaseLabel }}</span>
          <span v-if="props.gain" class="shrink-0 font-semibold" :class="GAIN_TEXT_CLASSES[props.gain.direction]">
            {{ props.gain.amountLabel }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType, Ref } from 'vue'
import type {
  GoupixDexSealedProductTileGain,
  GoupixDexSealedProductTileGainDirection,
  GoupixDexSealedProductTileProps,
} from '~/types/GoupixDexSealedProductTile'
import { sealedProductTypeIcon, sealedProductTypeLabel } from '~/utils/sealedProducts'

const props: GoupixDexSealedProductTileProps = defineProps({
  name: {
    type: String,
    required: true,
  },
  imageUrl: {
    type: String as PropType<string | null>,
    default: null,
  },
  productType: {
    type: String,
    required: true,
  },
  setName: {
    type: String as PropType<string | null>,
    default: null,
  },
  priceLabel: {
    type: String as PropType<string | null>,
    default: null,
  },
  purchaseLabel: {
    type: String as PropType<string | null>,
    default: null,
  },
  gain: {
    type: Object as PropType<GoupixDexSealedProductTileGain | null>,
    default: null,
  },
  ownedQuantity: {
    type: Number,
    default: 0,
  },
  isAddable: {
    type: Boolean,
    default: false,
  },
  isAdding: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits<{
  select: []
  add: []
}>()

const GAIN_BADGE_CLASSES: Record<GoupixDexSealedProductTileGainDirection, string> = {
  up: 'bg-success/15 text-success',
  down: 'bg-error/15 text-error',
  flat: 'bg-elevated text-muted',
}

const GAIN_TEXT_CLASSES: Record<GoupixDexSealedProductTileGainDirection, string> = {
  up: 'text-success',
  down: 'text-error',
  flat: 'text-muted',
}

// Certaines images listées par TCGplayer n'existent pas sur leur CDN : l'icône du type prend alors le relais.
const hasImageLoadFailed: Ref<boolean> = ref(false)

const productTypeAndSetLabel: ComputedRef<string> = computed((): string =>
  [sealedProductTypeLabel(props.productType), props.setName].filter(Boolean).join(' · '),
)

watch(
  (): string | null => props.imageUrl,
  (): void => {
    hasImageLoadFailed.value = false
  },
)
</script>
