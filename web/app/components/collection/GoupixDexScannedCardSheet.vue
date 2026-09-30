<template>
  <div
    class="border-white/10 bg-neutral-950/90 px-4 pt-4 text-white shadow-2xl backdrop-blur-xl"
    :class="
      props.isEmbedded
        ? 'rounded-2xl border pb-4'
        : 'rounded-t-3xl border-t pb-[max(1.5rem,env(safe-area-inset-bottom))]'
    "
  >
    <div class="flex gap-4">
      <div class="aspect-[63/88] w-24 shrink-0 overflow-hidden rounded-lg bg-white/10 shadow-lg">
        <GoupixDexCardImage
          :image-url="props.scannedCard.imageUrl"
          :tcgdex-card-id="props.scannedCard.decision.tcgdexCardId"
          :alt="cardName"
          img-class="h-full w-full object-cover"
        />
      </div>

      <div class="min-w-0 flex-1">
        <div class="flex items-start gap-2">
          <p class="min-w-0 flex-1 truncate pt-0.5 text-xl leading-tight font-bold">{{ cardName }}</p>
          <button
            type="button"
            class="-mt-1 -mr-1 flex size-9 shrink-0 cursor-pointer items-center justify-center rounded-full text-white/60 transition-colors hover:bg-white/10 hover:text-white"
            aria-label="Fermer la fiche"
            @click="emit('close')"
          >
            <UIcon name="i-lucide-x" class="size-5" />
          </button>
        </div>
        <p class="text-sm text-white/60 tabular-nums">{{ printedNumberLabel }}</p>
        <p v-if="setLabel" class="truncate text-sm text-white/60">{{ setLabel }}</p>
        <div
          v-else-if="props.scannedCard.isPreviewLoading"
          class="mt-1.5 h-3.5 w-32 animate-pulse rounded bg-white/10"
        />

        <div class="mt-2.5 flex flex-wrap items-center gap-1.5">
          <span
            v-if="marketPriceLabel"
            class="rounded-lg bg-emerald-500/15 px-2.5 py-1 text-lg leading-none font-semibold text-emerald-300 tabular-nums"
          >
            {{ marketPriceLabel }}
          </span>
          <span v-else-if="props.scannedCard.isPreviewLoading" class="h-7 w-16 animate-pulse rounded-lg bg-white/10" />
          <span
            v-if="ownedQuantity > 0"
            class="inline-flex items-center gap-1 rounded-lg bg-amber-400/15 px-2 py-1.5 text-xs leading-none font-semibold text-amber-200"
          >
            <UIcon name="i-lucide-library-big" class="size-3.5 shrink-0" />
            Déjà ×{{ ownedQuantity }} dans ma collection
          </span>
        </div>
      </div>
    </div>

    <button
      type="button"
      class="mt-4 flex h-14 w-full cursor-pointer items-center gap-3 rounded-2xl border px-3 text-left text-base font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50"
      :class="
        props.scannedCard.action === 'done'
          ? 'border-emerald-400/30 bg-emerald-500/15'
          : 'border-white/10 bg-white/10 active:bg-white/15'
      "
      :disabled="props.scannedCard.action === 'pending' || isAbsentFromCollection"
      @click="emit('confirm')"
    >
      <span
        class="flex size-9 shrink-0 items-center justify-center rounded-full"
        :class="{
          'bg-emerald-400/20 text-emerald-300': props.scannedCard.action === 'done',
          'bg-red-500/20 text-red-300': props.scannedCard.action !== 'done' && isCheckout,
          'bg-(--app-accent)/20 text-(--app-accent)': props.scannedCard.action !== 'done' && !isCheckout,
        }"
      >
        <UIcon :name="actionIcon" class="size-5" :class="{ 'animate-spin': props.scannedCard.action === 'pending' }" />
      </span>
      <span class="min-w-0 truncate">{{ actionLabel }}</span>
    </button>
    <p v-if="props.scannedCard.actionError" class="mt-2 text-xs text-red-300">
      {{ props.scannedCard.actionError }}
    </p>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType } from 'vue'
import type { GoupixDexScannedCardSheetProps } from '~/types/GoupixDexScannedCardSheet'
import type { ScannedCard, ScannedCardPreview } from '~/types/ScannedCardSheet'
import { readableSetLabel } from '~/utils/cards/readableSet'

const props: GoupixDexScannedCardSheetProps = defineProps({
  scannedCard: {
    type: Object as PropType<ScannedCard>,
    required: true,
  },
  isEmbedded: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits<{
  confirm: []
  close: []
}>()

const eur: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 2,
})

const cardName: ComputedRef<string> = computed(
  (): string => props.scannedCard.preview?.display_name || props.scannedCard.decision.name,
)

const printedNumberLabel: ComputedRef<string> = computed((): string => {
  const cardNumber: string = props.scannedCard.preview?.card_number ?? props.scannedCard.decision.localId
  const printedSetTotal: number | null = props.scannedCard.preview?.printed_set_total ?? null
  if (!/^\d+$/.test(cardNumber)) {
    return `#${cardNumber}`
  }
  if (!printedSetTotal) {
    return `#${cardNumber.padStart(3, '0')}`
  }
  const digitCount: number = Math.max(3, String(printedSetTotal).length)
  return `${cardNumber.padStart(digitCount, '0')}/${String(printedSetTotal).padStart(digitCount, '0')}`
})

const setLabel: ComputedRef<string> = computed((): string => {
  const preview: ScannedCardPreview | null = props.scannedCard.preview
  return preview ? readableSetLabel(preview.set_name, preview.set_code, preview.tcgdex_set_id) : ''
})

const marketPriceLabel: ComputedRef<string | null> = computed((): string | null => {
  const marketPrice: number | null | undefined = props.scannedCard.preview?.market_price_eur
  return marketPrice != null ? eur.format(marketPrice) : null
})

const ownedQuantity: ComputedRef<number> = computed((): number => props.scannedCard.ownedQuantity ?? 0)

const isCheckout: ComputedRef<boolean> = computed((): boolean => props.scannedCard.direction === 'out')

const isAbsentFromCollection: ComputedRef<boolean> = computed(
  (): boolean => isCheckout.value && props.scannedCard.ownedQuantity === 0,
)

const actionLabel: ComputedRef<string> = computed((): string => {
  switch (props.scannedCard.action) {
    case 'pending':
      return isCheckout.value ? 'Retrait en cours…' : 'Ajout en cours…'
    case 'done':
      return isCheckout.value ? 'Retirée de ma collection' : 'Ajoutée à ma collection'
    case 'failed':
      return 'Réessayer'
    default:
      if (isAbsentFromCollection.value) {
        return 'Absente de ma collection'
      }
      return isCheckout.value ? 'Retirer de ma collection' : 'Ajouter à ma collection'
  }
})

const actionIcon: ComputedRef<string> = computed((): string => {
  switch (props.scannedCard.action) {
    case 'pending':
      return 'i-lucide-loader-circle'
    case 'done':
      return 'i-lucide-check'
    case 'failed':
      return 'i-lucide-rotate-ccw'
    default:
      return isCheckout.value ? 'i-lucide-minus' : 'i-lucide-plus'
  }
})
</script>
