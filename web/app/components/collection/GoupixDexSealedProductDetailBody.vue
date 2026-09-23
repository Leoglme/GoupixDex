<template>
  <div>
    <div v-if="loading" class="flex items-center justify-center py-20">
      <UIcon name="i-lucide-loader-2" class="text-primary size-8 animate-spin" />
    </div>

    <div v-else-if="!product" class="space-y-3 py-16 text-center">
      <UIcon name="i-lucide-box" class="text-muted mx-auto size-10" />
      <p class="text-highlighted text-sm font-medium">Produit introuvable.</p>
    </div>

    <div v-else class="space-y-5">
      <!-- Aperçu -->
      <div class="flex gap-4">
        <div class="bg-muted/20 flex size-24 shrink-0 items-center justify-center overflow-hidden rounded-xl">
          <img
            v-if="product.image_url"
            :src="product.image_url"
            :alt="product.name"
            class="h-full w-full object-contain"
            referrerpolicy="no-referrer"
            decoding="async"
          />
          <UIcon v-else :name="sealedProductTypeIcon(product.product_type)" class="text-muted size-9" />
        </div>
        <div class="min-w-0 flex-1">
          <p class="text-highlighted text-base leading-snug font-semibold">{{ product.name }}</p>
          <p v-if="product.set_name" class="text-muted mt-0.5 truncate text-sm">{{ product.set_name }}</p>
          <div class="mt-2 flex flex-wrap items-center gap-1.5">
            <UBadge color="primary" variant="subtle" size="sm">{{
              sealedProductTypeLabel(product.product_type)
            }}</UBadge>
            <UBadge color="neutral" variant="subtle" size="sm">{{ languageLabel(product.language) }}</UBadge>
            <UBadge color="neutral" variant="soft" size="sm">×{{ product.quantity }}</UBadge>
          </div>
        </div>
      </div>

      <!-- Prix + plus-value -->
      <div class="border-default grid grid-cols-2 gap-3 rounded-xl border p-3">
        <div>
          <p class="app-label">Prix marché</p>
          <p class="text-highlighted mt-0.5 text-xl font-semibold tabular-nums">
            {{ product.market_price_eur != null ? eur.format(product.market_price_eur) : '—' }}
          </p>
        </div>
        <div>
          <p class="app-label">Plus-value</p>
          <p
            v-if="product.gain_percent != null"
            class="mt-0.5 text-xl font-semibold tabular-nums"
            :class="product.gain_percent >= 0 ? 'text-(--app-green)' : 'text-(--app-red)'"
          >
            {{ formatSignedPercent(product.gain_percent) }}
          </p>
          <p v-else class="text-muted mt-0.5 text-xl">—</p>
        </div>
      </div>

      <!-- Évolution du prix -->
      <section class="space-y-2">
        <div class="flex items-center justify-between">
          <p class="app-label">Évolution du prix</p>
          <span v-if="priceHistorySourceLabel" class="text-muted text-[10px]">{{ priceHistorySourceLabel }}</span>
        </div>
        <GoupixDexPriceHistoryChart :points="priceHistory?.points ?? []" />
      </section>

      <UButton
        v-if="cardmarketLink"
        :to="cardmarketLink"
        target="_blank"
        rel="noopener noreferrer"
        external
        color="neutral"
        variant="ghost"
        size="sm"
        icon="i-lucide-external-link"
        class="w-full"
      >
        Voir sur Cardmarket
      </UButton>

      <!-- Détails éditables -->
      <section class="border-default space-y-3 border-t pt-4">
        <p class="app-label">Détails</p>
        <UFormField label="Nom">
          <UInput v-model="nameDraft" class="w-full" />
        </UFormField>
        <div class="grid grid-cols-2 gap-2">
          <UFormField label="Type">
            <USelect v-model="typeDraft" :items="typeOptions" value-key="value" label-key="label" class="w-full" />
          </UFormField>
          <UFormField label="Langue">
            <USelect
              v-model="languageDraft"
              :items="languageItems"
              value-key="value"
              label-key="label"
              class="w-full"
            />
          </UFormField>
        </div>
        <UFormField label="Set / édition">
          <UInput v-model="setNameDraft" class="w-full" />
        </UFormField>
        <div class="grid grid-cols-3 gap-2">
          <UFormField label="Quantité">
            <UInputNumber v-model="quantityDraft" :min="1" :max="999" class="w-full" />
          </UFormField>
          <UFormField label="Achat (€)">
            <UInput v-model="purchaseText" type="number" min="0" step="0.01" placeholder="—" class="w-full" />
          </UFormField>
          <UFormField label="Marché (€)">
            <UInput v-model="marketText" type="number" min="0" step="0.01" placeholder="—" class="w-full" />
          </UFormField>
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

      <!-- Mise en vente -->
      <section class="border-default space-y-3 border-t pt-4">
        <div class="flex items-center justify-between gap-2">
          <p class="app-label">Mettre en vente</p>
          <UButton
            v-if="!prefill"
            size="xs"
            color="primary"
            variant="solid"
            icon="i-lucide-sparkles"
            :loading="loadingPrefill"
            @click="onPreparePrefill"
          >
            Préremplir
          </UButton>
          <UButton
            v-else
            size="xs"
            color="neutral"
            variant="soft"
            icon="i-lucide-refresh-cw"
            :loading="loadingPrefill"
            @click="onPreparePrefill(true)"
          >
            Rafraîchir
          </UButton>
        </div>

        <UAlert v-if="product.article_id" color="success" variant="subtle" icon="i-lucide-tag" title="Article créé">
          <template #description>
            <NuxtLink :to="`/articles/${product.article_id}`" class="text-primary text-sm underline underline-offset-2">
              Voir l'article #{{ product.article_id }}
            </NuxtLink>
          </template>
        </UAlert>

        <div v-if="prefill">
          <GoupixDexArticleForm ref="formRef" mode="create" :loading="submitting" @submit-create="onSubmitCreate" />
        </div>
        <p v-else-if="!product.article_id" class="text-muted text-sm">
          Génère un article prérempli (titre, prix suggéré) à publier sur tes marketplaces.
        </p>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import type {
  SealedArticlePrefillResponse,
  SealedPriceHistoryPoint,
  SealedPriceHistoryResponse,
  SealedProduct,
  SealedProductType,
} from '~/composables/useSealed'
import {
  formatSignedPercent,
  parseEuroAmount,
  sealedProductTypeIcon,
  sealedProductTypeLabel,
  SEALED_TYPE_OPTIONS,
} from '~/utils/sealedProducts'
import { cardmarketUrl } from '~/utils/cards/cardmarketUrl'

/**
 * Corps de fiche d'un produit scellé, partagé entre le drawer et la page.
 */
const props = defineProps({
  sealedId: {
    type: Number,
    required: true,
  },
})

const emit = defineEmits<{
  updated: [product: SealedProduct]
  deleted: [sealedId: number]
}>()

const { getSealed, getPriceHistory, patchSealed, deleteSealed, prepareArticlePrefill, attachArticle } = useSealed()
const { loadProductPriceHistory } = useSealedCatalog()
const { createArticle, publishArticleToVinted } = useArticles()
const { isDesktopApp } = useDesktopRuntime()
const toast = useToast()

const product = ref<SealedProduct | null>(null)
const priceHistory = ref<SealedPriceHistoryResponse | null>(null)
const priceHistorySource = ref<'cardmarket' | 'tcgplayer' | null>(null)
const loading = ref(true)
const savingDraft = ref(false)
const deleting = ref(false)
const prefill = ref<SealedArticlePrefillResponse | null>(null)
const loadingPrefill = ref(false)
const submitting = ref(false)
const formRef = ref<{
  applyCatalogPrefill: (p: SealedArticlePrefillResponse) => Promise<void>
  buildCreateFormData: () => FormData
} | null>(null)

const typeOptions = SEALED_TYPE_OPTIONS
const languageItems = [
  { label: 'Français', value: 'fr' },
  { label: 'Anglais', value: 'en' },
  { label: 'Japonais', value: 'ja' },
]

const nameDraft = ref('')
const typeDraft = ref<SealedProductType>('autre')
const setNameDraft = ref('')
const languageDraft = ref('fr')
const quantityDraft = ref(1)
const purchaseText = ref('')
const marketText = ref('')
const notesDraft = ref('')

const eur: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 2,
})

/** Lien Cardmarket : URL stockée si présente, sinon fiche via idProduct, sinon recherche par nom. */
const cardmarketLink = computed<string | null>(() => {
  const current = product.value
  if (!current) {
    return null
  }
  return current.cardmarket_url ?? cardmarketUrl({ idProduct: current.cardmarket_id_product, name: current.name })
})

/** Origine de la courbe affichée : tendance TCGplayer recalée sur le prix Cardmarket, tendance approximative, ou rien. */
const priceHistorySourceLabel = computed<string | null>(() => {
  if (priceHistorySource.value === 'tcgplayer') {
    return 'tendance TCGplayer · prix Cardmarket'
  }
  return priceHistory.value?.approximate ? 'tendance approximative' : null
})

const isDirty = computed<boolean>(() => {
  const current = product.value
  if (!current) {
    return false
  }
  return (
    nameDraft.value.trim() !== current.name ||
    typeDraft.value !== current.product_type ||
    setNameDraft.value.trim() !== (current.set_name ?? '') ||
    languageDraft.value !== current.language ||
    quantityDraft.value !== current.quantity ||
    (purchaseText.value.trim() || '') !==
      (current.purchase_price_eur != null ? String(current.purchase_price_eur) : '') ||
    (marketText.value.trim() || '') !== (current.market_price_eur != null ? String(current.market_price_eur) : '') ||
    notesDraft.value.trim() !== (current.notes ?? '')
  )
})

/**
 * Libellé de langue physique.
 * @param code - Code langue.
 * @returns Le nom de la langue.
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
 * Recopie les valeurs du produit dans les brouillons d'édition.
 * @param p - Produit chargé.
 */
function syncDrafts(p: SealedProduct): void {
  nameDraft.value = p.name
  typeDraft.value = (p.product_type as SealedProductType) ?? 'autre'
  setNameDraft.value = p.set_name ?? ''
  languageDraft.value = p.language
  quantityDraft.value = p.quantity
  purchaseText.value = p.purchase_price_eur != null ? String(p.purchase_price_eur) : ''
  marketText.value = p.market_price_eur != null ? String(p.market_price_eur) : ''
  notesDraft.value = p.notes ?? ''
}

/**
 * Charge le produit et son historique de prix.
 * @returns Résolue quand le produit est chargé.
 */
async function load(): Promise<void> {
  loading.value = true
  prefill.value = null
  try {
    const data = await getSealed(props.sealedId)
    product.value = data
    syncDrafts(data)
    void loadPriceHistory()
  } catch (e) {
    toast.add({ title: 'Produit scellé', description: apiErrorMessage(e), color: 'error' })
    product.value = null
  } finally {
    loading.value = false
  }
}

/**
 * Recale une série TCGplayer sur le prix marché Cardmarket : dernier point aligné sur `marketPriceEur`,
 * en conservant la forme (variations relatives). Cardmarket ne publie pas d'historique pour les scellés,
 * mais son prix du jour est la référence € pertinente — d'où cette combinaison forme TCGplayer / niveau Cardmarket.
 * @param points - Points datés TCGplayer (€, ordre croissant).
 * @param marketPriceEur - Prix marché Cardmarket cible, ou `null`.
 * @returns Série recalée, ou la série d'origine si le recalage est impossible.
 */
function rebaseToMarketPrice(
  points: SealedPriceHistoryPoint[],
  marketPriceEur: number | null,
): SealedPriceHistoryPoint[] {
  const lastPrice = points.length > 0 ? points[points.length - 1].price_eur : 0
  if (marketPriceEur === null || marketPriceEur <= 0 || lastPrice <= 0) {
    return points
  }
  const factor = marketPriceEur / lastPrice
  return points.map(
    (point): SealedPriceHistoryPoint => ({
      date: point.date,
      price_eur: Math.round(point.price_eur * factor * 100) / 100,
    }),
  )
}

/**
 * Charge la courbe : tendance TCGplayer (vrai historique de ventes) recalée sur le prix marché Cardmarket
 * affiché ; repli sur les relevés Cardmarket du produit possédé si TCGplayer n'a pas d'historique.
 * @returns Résolue quand la courbe est chargée ou l'échec acté.
 */
async function loadPriceHistory(): Promise<void> {
  const tcgplayerId = product.value?.tcgplayer_id
  if (tcgplayerId != null) {
    const tcgplayerPoints = await loadProductPriceHistory(tcgplayerId)
    if (tcgplayerPoints.length >= 2) {
      priceHistory.value = {
        points: rebaseToMarketPrice(tcgplayerPoints, product.value?.market_price_eur ?? null),
        approximate: false,
      }
      priceHistorySource.value = 'tcgplayer'
      return
    }
  }
  let cardmarketHistory: SealedPriceHistoryResponse | null = null
  try {
    cardmarketHistory = await getPriceHistory(props.sealedId)
  } catch {
    cardmarketHistory = null
  }
  priceHistory.value = cardmarketHistory
  priceHistorySource.value = cardmarketHistory ? 'cardmarket' : null
}

/**
 * Enregistre les modifications de la fiche.
 * @returns Résolue après enregistrement.
 */
async function onSaveDraft(): Promise<void> {
  if (!product.value) {
    return
  }
  savingDraft.value = true
  try {
    const updated = await patchSealed(product.value.id, {
      name: nameDraft.value.trim(),
      product_type: typeDraft.value,
      set_name: setNameDraft.value.trim() || null,
      language: languageDraft.value,
      quantity: quantityDraft.value,
      purchase_price_eur: parseEuroAmount(purchaseText.value),
      market_price_eur: parseEuroAmount(marketText.value),
      notes: notesDraft.value.trim() || null,
    })
    product.value = updated
    syncDrafts(updated)
    emit('updated', updated)
    toast.add({ title: 'Produit mis à jour', color: 'success' })
  } catch (e) {
    toast.add({ title: 'Mise à jour impossible', description: apiErrorMessage(e), color: 'error' })
  } finally {
    savingDraft.value = false
  }
}

/**
 * Supprime le produit de la collection.
 * @returns Résolue après suppression.
 */
async function onDelete(): Promise<void> {
  if (!product.value) {
    return
  }
  deleting.value = true
  try {
    const id = product.value.id
    await deleteSealed(id)
    emit('deleted', id)
    toast.add({ title: 'Produit retiré', color: 'success' })
  } catch (e) {
    toast.add({ title: 'Suppression impossible', description: apiErrorMessage(e), color: 'error' })
  } finally {
    deleting.value = false
  }
}

/**
 * Génère le préremplissage article (titre, prix suggéré) et l'applique au formulaire.
 * @param refreshPricing - Rafraîchit le prix depuis le guide (true par défaut).
 * @returns Résolue après application.
 */
async function onPreparePrefill(refreshPricing: boolean | Event = true): Promise<void> {
  const refresh = typeof refreshPricing === 'boolean' ? refreshPricing : true
  if (!product.value) {
    return
  }
  loadingPrefill.value = true
  try {
    const data = await prepareArticlePrefill(product.value.id, refresh)
    prefill.value = data
    await nextTick()
    await formRef.value?.applyCatalogPrefill(data)
    await load()
  } catch (e) {
    toast.add({ title: 'Préremplissage impossible', description: apiErrorMessage(e), color: 'error' })
  } finally {
    loadingPrefill.value = false
  }
}

/**
 * Crée l'article depuis le formulaire, le relie au produit et publie si desktop.
 * @param fd - Corps multipart de l'article.
 * @returns Résolue après création.
 */
async function onSubmitCreate(fd: FormData): Promise<void> {
  if (!product.value) {
    return
  }
  if (!isDesktopApp.value) {
    fd.set('publish_to_vinted', 'false')
  }
  submitting.value = true
  try {
    const { article, vinted } = await createArticle(fd)
    try {
      await attachArticle(product.value.id, article.id)
    } catch {
      /* lien best-effort */
    }
    if (isDesktopApp.value && vinted.desktop_local && vinted.stream_path) {
      try {
        await publishArticleToVinted(article.id)
      } catch (e) {
        toast.add({ title: 'Worker Vinted', description: apiErrorMessage(e), color: 'error' })
        await navigateTo('/articles')
        return
      }
      await navigateTo({ path: '/articles/listing-logs', query: { article: String(article.id), progress: 'local' } })
      return
    }
    toast.add({ title: 'Article créé depuis le produit', color: 'success' })
    await navigateTo(`/articles/${article.id}`)
  } catch (e) {
    toast.add({ title: 'Création impossible', description: apiErrorMessage(e), color: 'error' })
  } finally {
    submitting.value = false
  }
}

watch(
  () => props.sealedId,
  () => {
    void load()
  },
  { immediate: true },
)
</script>
