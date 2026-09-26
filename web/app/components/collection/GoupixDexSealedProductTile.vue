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
      <div class="mt-auto flex items-baseline justify-between gap-2 pt-2">
        <span class="text-muted truncate text-xs tabular-nums">{{ props.purchaseLabel }}</span>
        <span
          class="shrink-0 font-mono text-sm font-bold tabular-nums"
          :class="props.priceLabel ? 'text-highlighted' : 'text-(--app-faint)'"
        >
          {{ props.priceLabel ?? '—' }}
        </span>
      </div>
      <slot name="footer" />
    </div>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType, Ref } from 'vue'
import type { GoupixDexSealedProductTileProps } from '~/types/GoupixDexSealedProductTile'
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
