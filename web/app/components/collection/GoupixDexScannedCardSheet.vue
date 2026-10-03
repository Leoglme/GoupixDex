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
            class="-mt-1 -mr-1 flex size-9 shrink-0 cursor-pointer items-center justify-center rounded-full text-white/60 transition-colors hover:bg-white/10 hover:text-white disabled:cursor-not-allowed"
            :aria-label="props.scannedCard.addedEventIds.length ? 'Annuler l’ajout' : 'Fermer la fiche'"
            :disabled="props.scannedCard.action === 'pending' || props.scannedCard.isCancellingAdds"
            @click="emit('close')"
          >
            <UIcon
              :name="props.scannedCard.isCancellingAdds ? 'i-lucide-loader-circle' : 'i-lucide-x'"
              class="size-5"
              :class="{ 'animate-spin': props.scannedCard.isCancellingAdds }"
            />
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

    <div class="mt-4 flex flex-col gap-2">
      <button
        v-for="actionButton in actionButtons"
        :key="actionButton.key"
        type="button"
        class="flex h-14 w-full cursor-pointer items-center gap-3 rounded-2xl border px-3 text-left text-base font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50"
        :class="
          actionButtonState(actionButton) === 'done'
            ? 'border-emerald-400/30 bg-emerald-500/15'
            : 'border-white/10 bg-white/10 active:bg-white/15'
        "
        :disabled="isActionButtonDisabled(actionButton)"
        @click="emit('confirm', actionButton.binderId)"
      >
        <span
          class="flex size-9 shrink-0 items-center justify-center rounded-full"
          :class="{
            'bg-emerald-400/20 text-emerald-300': actionButtonState(actionButton) === 'done',
            'bg-red-500/20 text-red-300': actionButtonState(actionButton) !== 'done' && isCheckout,
            'bg-(--app-accent)/20 text-(--app-accent)': actionButtonState(actionButton) !== 'done' && !isCheckout,
          }"
        >
          <UIcon
            :name="actionButtonIcon(actionButton)"
            class="size-5"
            :class="{ 'animate-spin': actionButtonState(actionButton) === 'pending' }"
          />
        </span>
        <span class="min-w-0 truncate">{{ actionButtonLabel(actionButton) }}</span>
      </button>
    </div>
    <p v-if="props.scannedCard.actionError" class="mt-2 text-xs text-red-300">
      {{ props.scannedCard.actionError }}
    </p>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType } from 'vue'
import type { FillableBinderSlot } from '~/types/binders'
import type { GoupixDexScannedCardSheetProps, ScannedCardActionButton } from '~/types/GoupixDexScannedCardSheet'
import type { ScannedCard, ScannedCardAction, ScannedCardPreview } from '~/types/ScannedCardSheet'
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
  confirm: [binderId: number | null]
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

const fillableBinderSlots: ComputedRef<FillableBinderSlot[]> = computed((): FillableBinderSlot[] =>
  isCheckout.value ? [] : (props.scannedCard.preview?.fillable_binder_slots ?? []),
)

const collectionActionButton: ComputedRef<ScannedCardActionButton> = computed((): ScannedCardActionButton => {
  if (isCheckout.value) {
    return {
      key: 'collection',
      binderId: null,
      idleLabel: isAbsentFromCollection.value ? 'Absente de ma collection' : 'Retirer de ma collection',
      pendingLabel: 'Retrait en cours…',
      doneLabel: 'Retirée de ma collection',
      idleIcon: 'i-lucide-minus',
    }
  }
  return {
    key: 'collection',
    binderId: null,
    idleLabel: 'Ajouter à ma collection',
    pendingLabel: 'Ajout en cours…',
    doneLabel: 'Ajoutée à ma collection',
    idleIcon: 'i-lucide-plus',
  }
})

const actionButtons: ComputedRef<ScannedCardActionButton[]> = computed((): ScannedCardActionButton[] => [
  collectionActionButton.value,
  ...fillableBinderSlots.value.map(binderActionButton),
])

/**
 * Bouton qui ajoute un exemplaire et le range dans la pochette que lui garde un classeur.
 * @param {FillableBinderSlot} slot - Pochette du classeur que la carte peut remplir.
 * @returns {ScannedCardActionButton} Bouton « Ajouter au classeur … ».
 */
function binderActionButton(slot: FillableBinderSlot): ScannedCardActionButton {
  return {
    key: `binder-${slot.binder_id}`,
    binderId: slot.binder_id,
    idleLabel: `Ajouter au classeur ${slot.binder_name}`,
    pendingLabel: 'Rangement en cours…',
    doneLabel: `Rangée dans ${slot.binder_name}`,
    idleIcon: 'i-lucide-book-open',
  }
}

/**
 * État montré par un bouton : celui de l'action en cours quand c'est lui qui l'a lancée, sinon le repos.
 * @param {ScannedCardActionButton} actionButton - Bouton de la fiche.
 * @returns {ScannedCardAction} État à afficher.
 */
function actionButtonState(actionButton: ScannedCardActionButton): ScannedCardAction {
  return props.scannedCard.actionBinderId === actionButton.binderId ? props.scannedCard.action : 'idle'
}

/**
 * Indique si un bouton de la fiche doit être désactivé.
 * @param {ScannedCardActionButton} actionButton - Bouton de la fiche.
 * @returns {boolean} `true` quand le bouton doit être désactivé.
 */
function isActionButtonDisabled(actionButton: ScannedCardActionButton): boolean {
  if (props.scannedCard.action === 'pending' || props.scannedCard.isCancellingAdds) {
    return true
  }
  if (actionButton.binderId === null) {
    return isAbsentFromCollection.value
  }
  return actionButtonState(actionButton) === 'done'
}

/**
 * Libellé d'un bouton selon son état.
 * @param {ScannedCardActionButton} actionButton - Bouton de la fiche.
 * @returns {string} Libellé affiché.
 */
function actionButtonLabel(actionButton: ScannedCardActionButton): string {
  switch (actionButtonState(actionButton)) {
    case 'pending':
      return actionButton.pendingLabel
    case 'done':
      return actionButton.doneLabel
    case 'failed':
      return 'Réessayer'
    default:
      return actionButton.idleLabel
  }
}

/**
 * Icône d'un bouton selon son état.
 * @param {ScannedCardActionButton} actionButton - Bouton de la fiche.
 * @returns {string} Nom de l'icône.
 */
function actionButtonIcon(actionButton: ScannedCardActionButton): string {
  switch (actionButtonState(actionButton)) {
    case 'pending':
      return 'i-lucide-loader-circle'
    case 'done':
      return 'i-lucide-check'
    case 'failed':
      return 'i-lucide-rotate-ccw'
    default:
      return actionButton.idleIcon
  }
}
</script>
