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
          <img
            v-if="card.image_url"
            :src="card.image_url"
            :alt="card.display_name"
            class="h-full w-full object-contain"
            referrerpolicy="no-referrer"
            decoding="async"
          />
          <div v-else class="flex h-full items-center justify-center">
            <UIcon name="i-lucide-image-off" class="text-muted size-8" />
          </div>
        </div>
        <div class="min-w-0 flex-1">
          <p class="text-highlighted text-base leading-snug font-semibold">{{ card.display_name }}</p>
          <p class="text-muted mt-0.5 truncate text-sm">
            {{ card.set_name || card.tcgdex_set_id }} · #{{ card.card_number }}
          </p>
          <div class="mt-2 flex flex-wrap items-center gap-1.5">
            <UBadge color="primary" variant="subtle" size="sm">{{ languageLabel(card.language) }}</UBadge>
            <UBadge v-if="card.rarity" color="warning" variant="subtle" size="sm">{{ card.rarity }}</UBadge>
            <UBadge color="neutral" variant="soft" size="sm">×{{ card.quantity }}</UBadge>
          </div>
        </div>
      </div>

      <!-- Prix marché -->
      <div class="border-default rounded-xl border p-3">
        <p class="app-label">Prix marché</p>
        <p class="text-highlighted mt-0.5 text-xl font-semibold tabular-nums">
          {{ card.market_price_eur != null ? eur.format(card.market_price_eur) : '—' }}
        </p>
        <p v-if="card.market_price_eur != null" class="text-muted mt-0.5 text-xs">
          Cardmarket · {{ eur.format(lineMarketEur) }} pour {{ card.quantity }} exemplaire(s)
        </p>
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

        <UAlert v-if="card.article_id" color="success" variant="subtle" icon="i-lucide-tag" title="Article créé">
          <template #description>
            <NuxtLink :to="`/articles/${card.article_id}`" class="text-primary text-sm underline underline-offset-2">
              Voir l'article #{{ card.article_id }}
            </NuxtLink>
          </template>
        </UAlert>

        <div v-if="prefill">
          <GoupixDexArticleForm ref="formRef" mode="create" :loading="submitting" @submit-create="onSubmitCreate" />
        </div>
        <p v-else-if="!card.article_id" class="text-muted text-sm">
          Génère un article prérempli (titre, prix suggéré) à publier sur tes marketplaces.
        </p>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { CollectionArticlePrefillResponse, CollectionCard } from '~/composables/useCollection'
import type { GoupixPriceHistoryResponse } from '~/types/PriceHistory'

/**
 * Corps de fiche d'une carte de collection, partagé entre le drawer et la page.
 */
const props = defineProps({
  cardId: {
    type: Number,
    required: true,
  },
})

const emit = defineEmits<{
  updated: [card: CollectionCard]
  deleted: [cardId: number]
}>()

const {
  getCollectionCard,
  getCardPriceHistory,
  patchCollectionCard,
  deleteCollectionCard,
  prepareArticlePrefill,
  attachArticle,
} = useCollection()
const { createArticle, publishArticleToVinted } = useArticles()
const { isDesktopApp } = useDesktopRuntime()
const toast = useToast()

const card = ref<CollectionCard | null>(null)
const priceHistory = ref<GoupixPriceHistoryResponse | null>(null)
const loading = ref(true)
const savingDraft = ref(false)
const deleting = ref(false)
const prefill = ref<CollectionArticlePrefillResponse | null>(null)
const loadingPrefill = ref(false)
const submitting = ref(false)
const formRef = ref<{
  applyCatalogPrefill: (p: CollectionArticlePrefillResponse) => Promise<void>
  buildCreateFormData: () => FormData
} | null>(null)

const languageItems = [
  { label: 'Français', value: 'fr' },
  { label: 'Anglais', value: 'en' },
  { label: 'Japonais', value: 'ja' },
]

const quantityDraft = ref(1)
const languageDraft = ref('fr')
const notesDraft = ref('')

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

const isDirty = computed<boolean>(() => {
  const current = card.value
  if (!current) {
    return false
  }
  return (
    quantityDraft.value !== current.quantity ||
    languageDraft.value !== current.language ||
    notesDraft.value.trim() !== (current.notes ?? '')
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
}

/**
 * Charge la carte et son historique de prix.
 * @returns Résolue quand la carte est chargée.
 */
async function load(): Promise<void> {
  loading.value = true
  prefill.value = null
  try {
    const data = await getCollectionCard(props.cardId)
    card.value = data
    syncDrafts(data)
    void loadPriceHistory()
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
    })
    card.value = updated
    syncDrafts(updated)
    emit('updated', updated)
    toast.add({ title: 'Carte mise à jour', color: 'success' })
  } catch (e) {
    toast.add({ title: 'Mise à jour impossible', description: apiErrorMessage(e), color: 'error' })
  } finally {
    savingDraft.value = false
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
 * Génère le préremplissage article (titre, prix suggéré) et l'applique au formulaire.
 * @param refreshPricing - Rafraîchit le prix depuis le guide (true par défaut).
 * @returns Résolue après application.
 */
async function onPreparePrefill(refreshPricing: boolean | Event = true): Promise<void> {
  const refresh = typeof refreshPricing === 'boolean' ? refreshPricing : true
  if (!card.value) {
    return
  }
  loadingPrefill.value = true
  try {
    const data = await prepareArticlePrefill(card.value.id, refresh)
    prefill.value = data
    await nextTick()
    await formRef.value?.applyCatalogPrefill(data)
  } catch (e) {
    toast.add({ title: 'Préremplissage impossible', description: apiErrorMessage(e), color: 'error' })
  } finally {
    loadingPrefill.value = false
  }
}

/**
 * Crée l'article depuis le formulaire, le relie à la carte et publie si desktop.
 * @param fd - Corps multipart de l'article.
 * @returns Résolue après création.
 */
async function onSubmitCreate(fd: FormData): Promise<void> {
  if (!card.value) {
    return
  }
  if (!isDesktopApp.value) {
    fd.set('publish_to_vinted', 'false')
  }
  submitting.value = true
  try {
    const { article, vinted } = await createArticle(fd)
    try {
      await attachArticle(card.value.id, article.id)
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
    toast.add({ title: 'Article créé depuis la carte', color: 'success' })
    await navigateTo(`/articles/${article.id}`)
  } catch (e) {
    toast.add({ title: 'Création impossible', description: apiErrorMessage(e), color: 'error' })
  } finally {
    submitting.value = false
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
