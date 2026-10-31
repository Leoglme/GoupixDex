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
          :fallback-image-url="props.scannedCard.preview?.image_url"
          :tcgdex-card-id="props.scannedCard.decision.tcgdexCardId"
          :alt="cardName"
          img-class="h-full w-full object-cover"
        />
      </div>

      <div class="min-w-0 flex-1">
        <div class="flex items-start gap-2">
          <p v-if="cardName" class="min-w-0 flex-1 truncate pt-0.5 text-xl leading-tight font-bold">{{ cardName }}</p>
          <div v-else class="mt-0.5 h-6 min-w-0 flex-1 animate-pulse rounded bg-white/10" />
          <button
            type="button"
            class="-mt-1 -mr-1 flex size-9 shrink-0 cursor-pointer items-center justify-center rounded-full text-white/60 transition-colors hover:bg-white/10 hover:text-white disabled:cursor-not-allowed"
            aria-label="Fermer la fiche"
            :disabled="isWaitingForServer"
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
      :disabled="isWaitingForServer || isAbsentFromCollection"
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
        <UIcon
          :name="actionButtonIcon"
          class="size-5"
          :class="{ 'animate-spin': props.scannedCard.action === 'pending' }"
        />
      </span>
      <span class="min-w-0 truncate">{{ actionButtonLabel }}</span>
    </button>
    <GoupixDexScannedCardUndoAdd
      :adds-from-sheet="props.scannedCard.addsFromSheet"
      :is-undoing-last-add="props.scannedCard.isUndoingLastAdd"
      :is-disabled="isWaitingForServer"
      @undo="emit('undo')"
    />
    <p v-if="props.scannedCard.actionError" class="mt-2 text-xs text-red-300">
      {{ props.scannedCard.actionError }}
    </p>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType } from 'vue'
import type { GoupixDexScannedCardSheetProps, ScannedCardActionButton } from '~/types/GoupixDexScannedCardSheet'
import type { ScannedCard } from '~/types/ScannedCardSheet'
import { scannedCardName, scannedCardPrintedNumber, scannedCardSetName } from '~/utils/cards/scannedCardLabels'

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
  undo: []
  close: []
}>()

const eur: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 2,
})

const cardName: ComputedRef<string> = computed((): string => scannedCardName(props.scannedCard))

const printedNumberLabel: ComputedRef<string> = computed((): string => scannedCardPrintedNumber(props.scannedCard))

const setLabel: ComputedRef<string> = computed((): string => scannedCardSetName(props.scannedCard))

const marketPriceLabel: ComputedRef<string | null> = computed((): string | null => {
  const marketPrice: number | null | undefined = props.scannedCard.preview?.market_price_eur
  return marketPrice != null ? eur.format(marketPrice) : null
})

const ownedQuantity: ComputedRef<number> = computed((): number => props.scannedCard.ownedQuantity ?? 0)

const isCheckout: ComputedRef<boolean> = computed((): boolean => props.scannedCard.direction === 'out')

const isAbsentFromCollection: ComputedRef<boolean> = computed(
  (): boolean => isCheckout.value && props.scannedCard.ownedQuantity === 0,
)

const isWaitingForServer: ComputedRef<boolean> = computed(
  (): boolean => props.scannedCard.action === 'pending' || props.scannedCard.isUndoingLastAdd,
)

const actionButton: ComputedRef<ScannedCardActionButton> = computed((): ScannedCardActionButton => {
  if (isCheckout.value) {
    return {
      idleLabel: isAbsentFromCollection.value ? 'Absente de ma collection' : 'Retirer de ma collection',
      pendingLabel: 'Retrait en cours…',
      doneLabel: 'Retirée de ma collection',
      idleIcon: 'i-lucide-minus',
    }
  }
  return {
    idleLabel: 'Ajouter à ma collection',
    pendingLabel: 'Ajout en cours…',
    doneLabel: 'Ajoutée à ma collection',
    idleIcon: 'i-lucide-plus',
  }
})

const actionButtonLabel: ComputedRef<string> = computed((): string => {
  switch (props.scannedCard.action) {
    case 'pending':
      return actionButton.value.pendingLabel
    case 'done':
      return actionButton.value.doneLabel
    case 'failed':
      return 'Réessayer'
    default:
      return actionButton.value.idleLabel
  }
})

const actionButtonIcon: ComputedRef<string> = computed((): string => {
  switch (props.scannedCard.action) {
    case 'pending':
      return 'i-lucide-loader-circle'
    case 'done':
      return 'i-lucide-check'
    case 'failed':
      return 'i-lucide-rotate-ccw'
    default:
      return actionButton.value.idleIcon
  }
})
</script>
