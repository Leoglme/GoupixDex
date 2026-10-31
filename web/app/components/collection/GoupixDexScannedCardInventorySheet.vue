<template>
  <section
    aria-label="Où en est cette carte"
    class="border-white/10 bg-neutral-950/90 px-4 pt-4 text-white shadow-2xl backdrop-blur-xl"
    :class="
      props.isEmbedded
        ? 'rounded-2xl border pb-4'
        : 'rounded-t-3xl border-t pb-[max(1.5rem,env(safe-area-inset-bottom))] sm:rounded-3xl sm:border sm:pb-4'
    "
  >
    <div class="flex items-start gap-3.5">
      <div class="aspect-[63/88] w-14 shrink-0 overflow-hidden rounded-lg bg-white/10 shadow-lg">
        <GoupixDexCardImage
          :image-url="props.scannedCard.imageUrl"
          :fallback-image-url="props.scannedCard.preview?.image_url"
          :tcgdex-card-id="props.scannedCard.decision.tcgdexCardId"
          :alt="cardName"
          img-class="h-full w-full object-cover"
        />
      </div>
      <div class="min-w-0 flex-1 pt-1">
        <p v-if="cardName" class="truncate text-xl leading-tight font-bold">{{ cardName }}</p>
        <div v-else class="h-6 animate-pulse rounded bg-white/10" />
        <p class="mt-1 truncate text-sm text-white/60 tabular-nums">{{ cardReferenceLabel }}</p>
      </div>
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

    <ul v-if="props.scannedCard.preview" class="mt-3.5 space-y-0.5">
      <li v-for="saleStep in saleSteps" :key="saleStep.name" class="flex h-10 items-center gap-3">
        <span
          class="flex size-7 shrink-0 items-center justify-center rounded-full"
          :class="{
            'bg-emerald-400/20 text-emerald-300': saleStep.status === 'done',
            'border-2 border-(--app-accent)': saleStep.status === 'todo',
            'border-2 border-dashed border-white/25': saleStep.status === 'blocked',
            'bg-(--app-accent)/20 text-(--app-accent)': saleStep.status === 'in-progress',
          }"
        >
          <UIcon v-if="saleStep.status === 'done'" name="i-lucide-check" class="size-4" />
          <span v-else-if="saleStep.status === 'todo'" class="size-2 rounded-full bg-(--app-accent)" />
          <UIcon
            v-else-if="saleStep.status === 'in-progress'"
            name="i-lucide-loader-circle"
            class="size-4 animate-spin"
          />
        </span>
        <span
          class="min-w-0 flex-1 truncate text-base"
          :class="{
            'font-bold': saleStep.status === 'todo',
            'font-semibold': saleStep.status !== 'todo',
            'text-white/40': saleStep.status === 'blocked',
          }"
        >
          {{ saleStep.label }}
        </span>
        <span v-if="saleStep.detail" class="shrink-0 text-sm font-semibold text-white/60 tabular-nums">
          {{ saleStep.detail }}
        </span>
        <span v-if="saleStep.marketplaces.length" class="flex shrink-0 gap-1.5">
          <GoupixDexMarketplaceAppIcon
            v-for="stepMarketplace in saleStep.marketplaces"
            :key="stepMarketplace.marketplace"
            :marketplace="stepMarketplace.marketplace"
            :is-greyed-out="!stepMarketplace.isOnline && !stepMarketplace.isPublishing"
            :class="{ 'opacity-50': stepMarketplace.isPublishing }"
          />
        </span>
      </li>
    </ul>
    <div v-else-if="props.scannedCard.isPreviewLoading" class="mt-3.5 space-y-2">
      <div v-for="placeholderRow in 3" :key="placeholderRow" class="h-8 animate-pulse rounded-lg bg-white/10" />
    </div>
    <p v-else class="mt-3.5 text-sm text-white/60">Statut indisponible, rescannez la carte.</p>

    <button
      v-if="saleActionButton"
      type="button"
      class="mt-3.5 flex h-14 w-full cursor-pointer items-center gap-3 rounded-2xl border px-3 text-left transition-colors disabled:cursor-not-allowed"
      :class="[
        props.scannedCard.action === 'done'
          ? 'border-emerald-400/30 bg-emerald-500/15'
          : 'border-white/10 bg-white/10 active:bg-white/15',
        { 'opacity-50': isSaleActionBusy },
      ]"
      :disabled="isSaleActionBusy || props.scannedCard.action === 'done'"
      @click="onSaleActionClick"
    >
      <span
        class="flex size-9 shrink-0 items-center justify-center rounded-full"
        :class="
          props.scannedCard.action === 'done'
            ? 'bg-emerald-400/20 text-emerald-300'
            : 'bg-(--app-accent)/20 text-(--app-accent)'
        "
      >
        <UIcon :name="saleActionButton.icon" class="size-5" :class="{ 'animate-spin': isSaleActionBusy }" />
      </span>
      <span class="flex min-w-0 flex-1 flex-col">
        <span class="truncate text-base font-semibold">{{ saleActionButton.label }}</span>
        <span v-if="saleActionButton.hint" class="truncate text-xs text-white/60">{{ saleActionButton.hint }}</span>
      </span>
      <span v-if="saleActionButton.marketplaces.length" class="flex shrink-0 gap-1">
        <GoupixDexMarketplaceAppIcon
          v-for="marketplace in saleActionButton.marketplaces"
          :key="marketplace"
          :marketplace="marketplace"
        />
      </span>
    </button>
    <p
      v-else-if="saleStatusMessage"
      class="mt-3.5 flex h-14 items-center justify-center rounded-2xl px-3 text-center text-sm font-semibold"
      :class="saleStatusMessage.isSaleComplete ? 'bg-emerald-500/10 text-emerald-200' : 'bg-white/5 text-white/75'"
    >
      {{ saleStatusMessage.text }}
    </p>

    <GoupixDexScannedCardUndoAdd
      v-if="!linkedArticle"
      :adds-from-sheet="props.scannedCard.addsFromSheet"
      :is-undoing-last-add="props.scannedCard.isUndoingLastAdd"
      :is-disabled="isWaitingForServer"
      @undo="emit('undo')"
    />
    <p v-if="props.scannedCard.actionError" class="mt-2 text-xs text-red-300">
      {{ props.scannedCard.actionError }}
    </p>
  </section>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType } from 'vue'
import type {
  GoupixDexScannedCardInventorySheetProps,
  ScannedCardSaleActionButton,
  ScannedCardSaleStatusMessage,
  ScannedCardSaleStep,
  ScannedCardSaleStepMarketplace,
} from '~/types/GoupixDexScannedCardInventorySheet'
import type { Marketplace, MarketplaceSetupIssues } from '~/types/Marketplace'
import type { ScannedCard, ScannedCardLinkedArticle } from '~/types/ScannedCardSheet'
import { scannedCardName, scannedCardPrintedNumber, scannedCardSetName } from '~/utils/cards/scannedCardLabels'
import { MARKETPLACES, marketplaceNamesLabel } from '~/utils/marketplaces'

const props: GoupixDexScannedCardInventorySheetProps = defineProps({
  scannedCard: {
    type: Object as PropType<ScannedCard>,
    required: true,
  },
  publishingMarketplaces: {
    type: Array as PropType<Marketplace[]>,
    required: true,
  },
  marketplaceSetupIssues: {
    type: Object as PropType<MarketplaceSetupIssues>,
    required: true,
  },
  isOpeningListingWizard: {
    type: Boolean,
    default: false,
  },
  isEmbedded: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits<{
  addToCollection: []
  putOnline: []
  publish: [marketplaces: Marketplace[]]
  undo: []
  close: []
}>()

const ADD_TO_COLLECTION_BUTTON: ScannedCardSaleActionButton = {
  action: 'add-to-collection',
  label: 'Ajouter à ma collection',
  hint: null,
  icon: 'i-lucide-plus',
  marketplaces: [],
}
const PUT_ONLINE_BUTTON: ScannedCardSaleActionButton = {
  action: 'put-online',
  label: 'Mettre en ligne',
  hint: 'Prenez 2 photos, la fiche se remplit seule',
  icon: 'i-lucide-camera',
  marketplaces: [],
}

const cardName: ComputedRef<string> = computed((): string => scannedCardName(props.scannedCard))

const cardReferenceLabel: ComputedRef<string> = computed((): string =>
  [scannedCardPrintedNumber(props.scannedCard), scannedCardSetName(props.scannedCard)].filter(Boolean).join(' · '),
)

const ownedQuantity: ComputedRef<number> = computed((): number => props.scannedCard.ownedQuantity ?? 0)

const linkedArticle: ComputedRef<ScannedCardLinkedArticle | null> = computed((): ScannedCardLinkedArticle | null =>
  ownedQuantity.value > 0 ? (props.scannedCard.preview?.linked_article ?? null) : null,
)

const marketplacesNotOnline: ComputedRef<Marketplace[]> = computed((): Marketplace[] => {
  const article: ScannedCardLinkedArticle | null = linkedArticle.value
  return MARKETPLACES.filter(
    (marketplace: Marketplace): boolean => article === null || !isLinkedArticleOnline(article, marketplace),
  )
})

const marketplacesToPublish: ComputedRef<Marketplace[]> = computed((): Marketplace[] =>
  marketplacesNotOnline.value.filter(
    (marketplace: Marketplace): boolean =>
      !props.publishingMarketplaces.includes(marketplace) && props.marketplaceSetupIssues[marketplace] === null,
  ),
)

const saleSteps: ComputedRef<ScannedCardSaleStep[]> = computed((): ScannedCardSaleStep[] => [
  collectionSaleStep(),
  articleSaleStep(),
  onlineSaleStep(),
])

const nextSaleAction: ComputedRef<ScannedCardSaleActionButton | null> = computed(
  (): ScannedCardSaleActionButton | null => {
    if (!props.scannedCard.preview) {
      return null
    }
    if (ownedQuantity.value === 0) {
      return ADD_TO_COLLECTION_BUTTON
    }
    if (!linkedArticle.value) {
      return PUT_ONLINE_BUTTON
    }
    if (props.publishingMarketplaces.length || !marketplacesToPublish.value.length) {
      return null
    }
    const isPublishingEverywhere: boolean = marketplacesToPublish.value.length === MARKETPLACES.length
    return {
      action: 'publish',
      label: isPublishingEverywhere
        ? 'Publier partout'
        : `Publier sur ${marketplaceNamesLabel(marketplacesToPublish.value)}`,
      hint: null,
      icon: 'i-lucide-send',
      marketplaces: marketplacesToPublish.value,
    }
  },
)

const saleActionButton: ComputedRef<ScannedCardSaleActionButton | null> = computed(
  (): ScannedCardSaleActionButton | null => {
    if (props.scannedCard.action === 'pending') {
      return { ...ADD_TO_COLLECTION_BUTTON, label: 'Ajout en cours…', icon: 'i-lucide-loader-circle' }
    }
    if (props.scannedCard.action === 'done') {
      return { ...ADD_TO_COLLECTION_BUTTON, label: 'Ajoutée à ma collection', icon: 'i-lucide-check' }
    }
    const nextAction: ScannedCardSaleActionButton | null = nextSaleAction.value
    if (nextAction?.action === 'add-to-collection' && props.scannedCard.action === 'failed') {
      return { ...nextAction, label: 'Réessayer', icon: 'i-lucide-rotate-ccw' }
    }
    if (nextAction?.action === 'put-online' && props.isOpeningListingWizard) {
      return { ...nextAction, icon: 'i-lucide-loader-circle' }
    }
    return nextAction
  },
)

const isSaleActionBusy: ComputedRef<boolean> = computed(
  (): boolean =>
    props.scannedCard.action === 'pending' ||
    (nextSaleAction.value?.action === 'put-online' && props.isOpeningListingWizard),
)

const saleStatusMessage: ComputedRef<ScannedCardSaleStatusMessage | null> = computed(
  (): ScannedCardSaleStatusMessage | null => {
    if (!linkedArticle.value || saleActionButton.value) {
      return null
    }
    if (props.publishingMarketplaces.length) {
      return { text: 'C’est lancé, passez à la carte suivante', isSaleComplete: false }
    }
    const blockedMarketplace: Marketplace | undefined = marketplacesNotOnline.value[0]
    if (!blockedMarketplace) {
      return { text: 'Rien à faire, passez à la carte suivante', isSaleComplete: true }
    }
    return { text: props.marketplaceSetupIssues[blockedMarketplace] ?? '', isSaleComplete: false }
  },
)

const isWaitingForServer: ComputedRef<boolean> = computed(
  (): boolean => props.scannedCard.action === 'pending' || props.scannedCard.isUndoingLastAdd,
)

/**
 * Vrai quand l'article lié à la carte est en ligne sur la marketplace.
 * @param {ScannedCardLinkedArticle} article - Article lié à un exemplaire de la carte.
 * @param {Marketplace} marketplace - Marketplace regardée.
 * @returns {boolean} Vrai si l'annonce y est publiée.
 */
function isLinkedArticleOnline(article: ScannedCardLinkedArticle, marketplace: Marketplace): boolean {
  const isOnlineByMarketplace: Record<Marketplace, boolean> = {
    vinted: article.published_on_vinted,
    ebay: article.published_on_ebay,
    leboncoin: article.published_on_leboncoin,
  }
  return isOnlineByMarketplace[marketplace]
}

/**
 * Première ligne de la fiche : la carte est-elle dans ma collection, et en combien d'exemplaires.
 * @returns {ScannedCardSaleStep} Ligne « collection ».
 */
function collectionSaleStep(): ScannedCardSaleStep {
  if (ownedQuantity.value > 0) {
    return {
      name: 'collection',
      status: 'done',
      label: 'Dans ma collection',
      detail: `×${ownedQuantity.value}`,
      marketplaces: [],
    }
  }
  return { name: 'collection', status: 'todo', label: 'Pas dans ma collection', detail: null, marketplaces: [] }
}

/**
 * Deuxième ligne : l'article de la carte, retiré de la vente ou non ; bloquée tant que la carte n'est pas dans la collection.
 * @returns {ScannedCardSaleStep} Ligne « article ».
 */
function articleSaleStep(): ScannedCardSaleStep {
  const article: ScannedCardLinkedArticle | null = linkedArticle.value
  if (ownedQuantity.value === 0) {
    return { name: 'article', status: 'blocked', label: 'Pas d’article', detail: null, marketplaces: [] }
  }
  if (!article) {
    return { name: 'article', status: 'todo', label: 'Pas encore d’article', detail: null, marketplaces: [] }
  }
  return {
    name: 'article',
    status: 'done',
    label: `Article #${article.id}`,
    detail: article.offers_for_sale ? null : 'retiré',
    marketplaces: [],
  }
}

/**
 * Troisième ligne : où l'article est en ligne, avec l'icône de chaque marketplace ; bloquée tant qu'il n'y a pas d'article.
 * @returns {ScannedCardSaleStep} Ligne « en ligne ».
 */
function onlineSaleStep(): ScannedCardSaleStep {
  const article: ScannedCardLinkedArticle | null = linkedArticle.value
  const marketplaces: ScannedCardSaleStepMarketplace[] = MARKETPLACES.map(
    (marketplace: Marketplace): ScannedCardSaleStepMarketplace => ({
      marketplace,
      isOnline: article !== null && isLinkedArticleOnline(article, marketplace),
      isPublishing: article !== null && props.publishingMarketplaces.includes(marketplace),
    }),
  )
  if (!article) {
    return { name: 'online', status: 'blocked', label: 'Pas en ligne', detail: null, marketplaces }
  }
  if (props.publishingMarketplaces.length) {
    return { name: 'online', status: 'in-progress', label: 'Publication en cours…', detail: null, marketplaces }
  }
  if (!marketplacesNotOnline.value.length) {
    return { name: 'online', status: 'done', label: 'En ligne partout', detail: null, marketplaces }
  }
  if (marketplacesNotOnline.value.length === MARKETPLACES.length) {
    return { name: 'online', status: 'todo', label: 'En ligne nulle part', detail: null, marketplaces }
  }
  return {
    name: 'online',
    status: 'todo',
    label: `Pas sur ${marketplaceNamesLabel(marketplacesNotOnline.value)}`,
    detail: null,
    marketplaces,
  }
}

/**
 * Lance l'étape proposée par le bouton : ajout à la collection, mise en ligne (photos), ou publication.
 * @returns {void}
 */
function onSaleActionClick(): void {
  const nextAction: ScannedCardSaleActionButton | null = nextSaleAction.value
  if (!nextAction || isSaleActionBusy.value) {
    return
  }
  if (nextAction.action === 'add-to-collection') {
    emit('addToCollection')
  } else if (nextAction.action === 'put-online') {
    emit('putOnline')
  } else {
    emit('publish', nextAction.marketplaces)
  }
}
</script>
