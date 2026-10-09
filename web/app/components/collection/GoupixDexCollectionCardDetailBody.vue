<template>
  <div>
    <div v-if="loading" class="flex items-center justify-center py-20">
      <UIcon name="i-lucide-loader-2" class="text-primary size-8 animate-spin" />
    </div>

    <div v-else-if="!card" class="space-y-3 py-16 text-center">
      <UIcon name="i-lucide-album-x" class="text-muted mx-auto size-10" />
      <p class="text-highlighted text-sm font-medium">Carte introuvable.</p>
    </div>

    <div v-else class="space-y-5">
      <!-- Aperçu -->
      <div class="flex gap-4">
        <div class="bg-muted/20 aspect-[63/88] w-24 shrink-0 overflow-hidden rounded-xl">
          <GoupixDexCardImage
            :image-url="card.image_url"
            :tcgdex-card-id="card.tcgdex_card_id"
            :alt="card.display_name"
          />
        </div>
        <div class="min-w-0 flex-1">
          <p class="text-highlighted text-base leading-snug font-semibold">{{ card.display_name }}</p>
          <p class="text-muted mt-0.5 truncate text-sm">
            {{ readableSetLabel(card.set_name, card.set_code, card.tcgdex_set_id) }} · #{{ card.card_number }}
          </p>
          <p v-if="hasJapanese(card.set_name)" class="text-muted truncate text-[11px] opacity-70">
            {{ card.set_name }}
          </p>
          <div class="mt-2 flex flex-wrap items-center gap-1.5">
            <UBadge color="primary" variant="subtle" size="sm">{{ languageLabel(card.language) }}</UBadge>
            <UBadge v-if="card.rarity" color="warning" variant="subtle" size="sm">{{ card.rarity }}</UBadge>
            <UBadge color="neutral" variant="soft" size="sm">×{{ card.quantity }}</UBadge>
          </div>
        </div>
      </div>

      <UButton
        v-if="card.article_id"
        color="neutral"
        variant="soft"
        size="lg"
        block
        icon="i-lucide-tag"
        @click="openLinkedArticle"
      >
        Voir l'article #{{ card.article_id }}
      </UButton>
      <UButton v-else color="primary" size="lg" block icon="i-lucide-camera" @click="isListingWizardOpen = true">
        Mettre en ligne
      </UButton>

      <UButton
        v-for="binderSlot in fillableBinderSlots"
        :key="binderSlot.binder_id"
        color="primary"
        variant="soft"
        icon="i-lucide-book-open"
        block
        :loading="placingBinderId === binderSlot.binder_id"
        :disabled="placingBinderId !== null"
        @click="onPlaceInBinder(binderSlot)"
      >
        Ajouter au classeur {{ binderSlot.binder_name }}
      </UButton>

      <!-- Changer la carte (uniquement quand ouverte depuis une pochette de classeur) -->
      <UButton v-if="pocket" color="primary" variant="soft" icon="i-lucide-replace" block @click="emit('change-card')">
        Changer la carte de cette pochette
      </UButton>

      <!-- Prix marché + plus-value -->
      <div class="border-default space-y-3 rounded-xl border p-3">
        <div class="grid grid-cols-2 gap-3">
          <div>
            <p class="app-label">Prix marché</p>
            <p class="text-highlighted mt-0.5 text-xl font-semibold tabular-nums">
              {{ card.market_price_eur != null ? eur.format(card.market_price_eur) : '—' }}
            </p>
          </div>
          <div>
            <p class="app-label">Plus-value</p>
            <p
              v-if="card.gain_percent != null"
              class="mt-0.5 text-xl font-semibold tabular-nums"
              :class="card.gain_percent >= 0 ? 'text-(--app-green)' : 'text-(--app-red)'"
            >
              {{ formatSignedPercent(card.gain_percent) }}
            </p>
            <p v-else class="text-muted mt-0.5 text-xl">—</p>
          </div>
        </div>
        <p v-if="card.purchase_price_eur != null" class="text-muted text-xs">
          Acheté {{ eur.format(card.purchase_price_eur) }}
          <template v-if="card.gain_eur != null">
            · {{ card.gain_eur >= 0 ? '+' : '' }}{{ eur.format(card.gain_eur) }} sur {{ card.quantity }} ex.
          </template>
        </p>
        <p v-else-if="card.market_price_eur != null" class="text-muted text-xs">
          Cardmarket · {{ eur.format(lineMarketEur) }} pour {{ card.quantity }} exemplaire(s)
        </p>
        <p v-if="card.scan_market_price_eur != null" class="text-muted text-xs">
          Au scan {{ eur.format(card.scan_market_price_eur) }}
          <template v-if="sinceScanPercent != null"> · {{ formatSignedPercent(sinceScanPercent) }} depuis</template>
        </p>
        <UButton
          :to="cardmarketLink"
          target="_blank"
          rel="noopener noreferrer"
          color="neutral"
          variant="subtle"
          size="xs"
          icon="i-lucide-external-link"
        >
          Voir sur Cardmarket
        </UButton>
      </div>

      <!-- Évolution du prix -->
      <section class="space-y-2">
        <div class="flex items-center justify-between">
          <p class="app-label">Évolution du prix</p>
          <span v-if="priceHistory?.approximate" class="text-muted text-[10px]">tendance approximative</span>
        </div>
        <GoupixDexPriceHistoryChart :points="priceHistory?.points ?? []" />
      </section>

      <!-- Détails éditables -->
      <section class="border-default space-y-3 border-t pt-4">
        <p class="app-label">Détails</p>
        <div class="grid grid-cols-2 gap-2">
          <UFormField label="Quantité">
            <UInputNumber v-model="quantityDraft" :min="1" :max="999" class="w-full" />
          </UFormField>
          <UFormField label="Langue physique">
            <USelect
              v-model="languageDraft"
              :items="languageItems"
              value-key="value"
              label-key="label"
              class="w-full"
            />
          </UFormField>
        </div>
        <div class="grid grid-cols-2 gap-2">
          <UFormField label="Prix d'achat (€)" hint="plus-value">
            <UInput v-model="purchaseText" type="text" inputmode="decimal" placeholder="—" class="w-full" />
          </UFormField>
          <UFormField label="Prix marché au scan (€)">
            <UInput v-model="scanMarketText" type="text" inputmode="decimal" placeholder="—" class="w-full" />
          </UFormField>
        </div>
        <div class="flex items-end gap-2">
          <UFormField
            label="Prix marché (€)"
            :hint="card.market_price_overridden ? 'saisi à la main' : 'corrige un prix erroné'"
            class="flex-1"
          >
            <UInput v-model="marketText" type="text" inputmode="decimal" placeholder="Auto" class="w-full" />
          </UFormField>
          <UButton
            v-if="card.market_price_overridden"
            color="neutral"
            variant="soft"
            size="md"
            icon="i-lucide-rotate-ccw"
            :loading="resettingPrice"
            title="Repasser le prix en automatique (Cardmarket)"
            @click="onResetPrice"
          >
            Auto
          </UButton>
        </div>
        <UFormField label="Notes">
          <UTextarea v-model="notesDraft" :rows="2" class="w-full" />
        </UFormField>
        <div class="flex flex-wrap items-center gap-2">
          <UButton
            color="primary"
            variant="soft"
            icon="i-lucide-save"
            :loading="savingDraft"
            :disabled="!isDirty"
            @click="onSaveDraft"
          >
            Enregistrer
          </UButton>
          <UButton color="error" variant="ghost" icon="i-lucide-trash-2" :loading="deleting" @click="onDelete">
            Retirer
          </UButton>
        </div>
      </section>
    </div>

    <GoupixDexCollectionCardListingWizard
      v-if="card"
      :open="isListingWizardOpen"
      :card="card"
      @close="isListingWizardOpen = false"
      @created="onListingArticleCreated"
    />
  </div>
</template>

<script setup lang="ts">
import type { PropType, Ref } from 'vue'
import type { Article } from '~/composables/useArticles'
import type { CollectionCard } from '~/composables/useCollection'
import type { FillableBinderSlot } from '~/types/binders'
import type { GoupixBinderPocketRef } from '~/types/GoupixDrawerStack'
import type { GoupixPriceHistoryResponse } from '~/types/PriceHistory'
import { cardmarketUrl } from '~/utils/cards/cardmarketUrl'
import { formatSignedPercent, parseEuroAmount } from '~/utils/sealedProducts'
import { hasJapanese, readableSetLabel } from '~/utils/cards/readableSet'

/**
 * Corps de fiche d'une carte de collection, partagé entre le drawer et la page.
 */
const props = defineProps({
  cardId: {
    type: Number,
    required: true,
  },
  pocket: {
    type: Object as PropType<GoupixBinderPocketRef | null>,
    default: null,
  },
})

const emit = defineEmits<{
  updated: [card: CollectionCard]
  deleted: [cardId: number]
  'change-card': []
}>()

const {
  getCollectionCard,
  getCardPriceHistory,
  getCardBinderSlots,
  placeCardInBinder,
  patchCollectionCard,
  deleteCollectionCard,
} = useCollection()
const { openArticle } = useOpenArticleDrawer()
const toast = useToast()

const card = ref<CollectionCard | null>(null)
const priceHistory = ref<GoupixPriceHistoryResponse | null>(null)
const loading = ref(true)
const savingDraft = ref(false)
const deleting = ref(false)
const resettingPrice = ref(false)
const isListingWizardOpen: Ref<boolean> = ref(false)
const fillableBinderSlots: Ref<FillableBinderSlot[]> = ref([])
const placingBinderId: Ref<number | null> = ref(null)

const languageItems = [
  { label: 'Français', value: 'fr' },
  { label: 'Anglais', value: 'en' },
  { label: 'Japonais', value: 'ja' },
]

const quantityDraft = ref(1)
const languageDraft = ref('fr')
const notesDraft = ref('')
const purchaseText = ref('')
const scanMarketText = ref('')
const marketText = ref('')

const eur: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 2,
})

const lineMarketEur = computed<number>(() => {
  const price = card.value?.market_price_eur
  if (price == null) {
    return 0
  }
  return price * (card.value?.quantity ?? 1)
})

const cardmarketLink = computed<string>(() =>
  cardmarketUrl({
    idProduct: card.value?.cardmarket_id_product,
    name: card.value?.display_name ?? '',
    localId: card.value?.card_number,
  }),
)

const sinceScanPercent = computed<number | null>(() => {
  const scanPrice = card.value?.scan_market_price_eur
  const marketPrice = card.value?.market_price_eur
  if (scanPrice == null || marketPrice == null || scanPrice <= 0) {
    return null
  }
  return (marketPrice / scanPrice - 1) * 100
})

const isMarketPriceDirty = computed<boolean>(
  () => parseEuroAmount(marketText.value) !== (card.value?.market_price_eur ?? null),
)

const isDirty = computed<boolean>(() => {
  const current = card.value
  if (!current) {
    return false
  }
  return (
    quantityDraft.value !== current.quantity ||
    languageDraft.value !== current.language ||
    notesDraft.value.trim() !== (current.notes ?? '') ||
    parseEuroAmount(purchaseText.value) !== current.purchase_price_eur ||
    parseEuroAmount(scanMarketText.value) !== current.scan_market_price_eur ||
    isMarketPriceDirty.value
  )
})

/**
 * Libellé de langue physique.
 * @param code - Code langue.
 * @returns Le nom complet de la langue.
 */
function languageLabel(code: string): string {
  switch (code) {
    case 'fr':
      return 'Français'
    case 'en':
      return 'Anglais'
    case 'ja':
      return 'Japonais'
    default:
      return code.toUpperCase()
  }
}

/**
 * Recopie les valeurs de la carte dans les brouillons d'édition.
 * @param c - Carte chargée.
 */
function syncDrafts(c: CollectionCard): void {
  quantityDraft.value = c.quantity
  languageDraft.value = c.language
  notesDraft.value = c.notes ?? ''
  purchaseText.value = c.purchase_price_eur != null ? String(c.purchase_price_eur) : ''
  scanMarketText.value = c.scan_market_price_eur != null ? String(c.scan_market_price_eur) : ''
  marketText.value = c.market_price_eur != null ? String(c.market_price_eur) : ''
}

/**
 * Charge la carte et son historique de prix.
 * @returns Résolue quand la carte est chargée.
 */
async function load(): Promise<void> {
  loading.value = true
  try {
    const data = await getCollectionCard(props.cardId)
    card.value = data
    syncDrafts(data)
    void loadPriceHistory()
    loadFillableBinderSlots()
  } catch (e) {
    toast.add({ title: 'Carte de collection', description: apiErrorMessage(e), color: 'error' })
    card.value = null
  } finally {
    loading.value = false
  }
}

/**
 * Charge la courbe de prix (best-effort, n'empêche pas l'affichage de la fiche).
 * @returns Résolue quand la courbe est chargée ou l'échec acté.
 */
async function loadPriceHistory(): Promise<void> {
  try {
    priceHistory.value = await getCardPriceHistory(props.cardId)
  } catch {
    priceHistory.value = null
  }
}

/**
 * Charge, sans bloquer la fiche, les classeurs Pokédex qui gardent une pochette vide pour cette carte.
 * @returns {Promise<void>} Résolue quand les pochettes sont chargées ou l'échec acté.
 */
async function loadFillableBinderSlots(): Promise<void> {
  try {
    fillableBinderSlots.value = await getCardBinderSlots(props.cardId)
  } catch {
    fillableBinderSlots.value = []
  }
}

/**
 * Range la carte dans la pochette vide de son Pokémon, dans le classeur choisi.
 * @param {FillableBinderSlot} binderSlot - Pochette proposée par le classeur.
 * @returns {Promise<void>} Résolue après le rangement, ou l'échec affiché.
 */
async function onPlaceInBinder(binderSlot: FillableBinderSlot): Promise<void> {
  if (!card.value) {
    return
  }
  placingBinderId.value = binderSlot.binder_id
  try {
    await placeCardInBinder(card.value.id, binderSlot.binder_id)
    fillableBinderSlots.value = fillableBinderSlots.value.filter(
      (slot: FillableBinderSlot): boolean => slot.binder_id !== binderSlot.binder_id,
    )
    emit('updated', card.value)
    toast.add({ title: `Rangée dans ${binderSlot.binder_name}`, color: 'success' })
  } catch (e) {
    toast.add({ title: 'Rangement impossible', description: apiErrorMessage(e), color: 'error' })
    loadFillableBinderSlots()
  } finally {
    placingBinderId.value = null
  }
}

/**
 * Enregistre les modifications de la fiche.
 * @returns Résolue après enregistrement.
 */
async function onSaveDraft(): Promise<void> {
  if (!card.value) {
    return
  }
  savingDraft.value = true
  try {
    const updated = await patchCollectionCard(card.value.id, {
      quantity: quantityDraft.value,
      language: languageDraft.value,
      notes: notesDraft.value.trim() || null,
      purchase_price_eur: parseEuroAmount(purchaseText.value),
      scan_market_price_eur: parseEuroAmount(scanMarketText.value),
      // Envoyé seulement s'il a changé : sinon le prix passerait en « saisi à la main ».
      ...(isMarketPriceDirty.value ? { market_price_eur: parseEuroAmount(marketText.value) } : {}),
    })
    card.value = updated
    syncDrafts(updated)
    emit('updated', updated)
    toast.add({ title: 'Carte mise à jour', color: 'success' })
    loadFillableBinderSlots()
  } catch (e) {
    toast.add({ title: 'Mise à jour impossible', description: apiErrorMessage(e), color: 'error' })
  } finally {
    savingDraft.value = false
  }
}

/**
 * Repasse le prix marché en automatique (efface la saisie manuelle, relit le guide Cardmarket).
 * @returns Résolue après remise à zéro.
 */
async function onResetPrice(): Promise<void> {
  if (!card.value) {
    return
  }
  resettingPrice.value = true
  try {
    const updated = await patchCollectionCard(card.value.id, { reset_market_price: true })
    card.value = updated
    syncDrafts(updated)
    emit('updated', updated)
    toast.add({ title: 'Prix repassé en automatique', color: 'success' })
  } catch (e) {
    toast.add({ title: 'Réinitialisation impossible', description: apiErrorMessage(e), color: 'error' })
  } finally {
    resettingPrice.value = false
  }
}

/**
 * Supprime la carte de la collection.
 * @returns Résolue après suppression.
 */
async function onDelete(): Promise<void> {
  if (!card.value) {
    return
  }
  deleting.value = true
  try {
    const id = card.value.id
    await deleteCollectionCard(id)
    emit('deleted', id)
    toast.add({ title: 'Carte retirée', color: 'success' })
  } catch (e) {
    toast.add({ title: 'Suppression impossible', description: apiErrorMessage(e), color: 'error' })
  } finally {
    deleting.value = false
  }
}

/**
 * Ouvre l'article lié dans le drawer, par-dessus la collection.
 * @returns {void}
 */
function openLinkedArticle(): void {
  const articleId: number | null | undefined = card.value?.article_id
  if (articleId) {
    openArticle(articleId)
  }
}

/**
 * Ferme la mise en ligne et relit la carte, désormais reliée à son article.
 * @param {Article} article - Article créé depuis la carte.
 * @returns {Promise<void>} Résolue quand la carte est relue.
 */
async function onListingArticleCreated(article: Article): Promise<void> {
  isListingWizardOpen.value = false
  if (card.value) {
    card.value = { ...card.value, article_id: article.id }
  }
  try {
    const refreshedCard: CollectionCard = await getCollectionCard(props.cardId)
    card.value = refreshedCard
    syncDrafts(refreshedCard)
    emit('updated', refreshedCard)
  } catch {
    // La fiche affiche déjà le lien vers l'article : la relecture n'est qu'un rafraîchissement.
  }
}

watch(
  () => props.cardId,
  () => {
    void load()
  },
  { immediate: true },
)
</script>
