<template>
  <UDashboardPanel id="sealed-product-page">
    <template #header>
      <UDashboardNavbar title="Produit scellé">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton to="/collection/produits" color="neutral" variant="ghost" icon="i-lucide-arrow-left">
            Produits scellés
          </UButton>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="app-dashboard-page w-full">
        <div v-if="loading" class="flex items-center justify-center py-20">
          <UIcon name="i-lucide-loader-2" class="text-primary size-10 animate-spin" />
        </div>

        <template v-else-if="product">
          <div class="grid gap-4 lg:grid-cols-[minmax(0,360px)_1fr] lg:items-start lg:gap-6">
            <UCard class="ring-default ring-1" :ui="{ body: 'p-4 sm:p-5 space-y-4' }">
              <div class="bg-muted/20 mx-auto aspect-square w-full max-w-[300px] overflow-hidden rounded-xl">
                <img
                  v-if="product.image_url"
                  :src="product.image_url"
                  :alt="product.name"
                  class="h-full w-full object-contain"
                  referrerpolicy="no-referrer"
                  decoding="async"
                />
                <div v-else class="flex h-full items-center justify-center">
                  <UIcon name="i-lucide-box" class="text-muted size-10" />
                </div>
              </div>

              <div class="space-y-1.5">
                <p class="text-highlighted text-lg leading-snug font-semibold">{{ product.name }}</p>
                <p class="text-muted text-sm">{{ product.set_name || '—' }}</p>
                <div class="flex flex-wrap items-center gap-1.5 pt-1">
                  <UBadge color="primary" variant="subtle" size="sm">{{
                    sealedProductTypeLabel(product.product_type)
                  }}</UBadge>
                  <UBadge color="neutral" variant="subtle" size="sm">{{ languageLabel(product.language) }}</UBadge>
                  <UBadge color="neutral" variant="soft" size="sm">×{{ product.quantity }}</UBadge>
                </div>
              </div>

              <div class="border-default grid grid-cols-2 gap-3 rounded-lg border p-3">
                <div>
                  <p class="app-label">Prix marché</p>
                  <p class="text-highlighted mt-0.5 text-lg font-semibold tabular-nums">
                    {{ product.market_price_eur != null ? eur.format(product.market_price_eur) : '—' }}
                  </p>
                </div>
                <div>
                  <p class="app-label">Plus-value</p>
                  <p
                    v-if="product.gain_percent != null"
                    class="mt-0.5 text-lg font-semibold tabular-nums"
                    :class="product.gain_percent >= 0 ? 'text-(--app-green)' : 'text-(--app-red)'"
                  >
                    {{ formatSignedPercent(product.gain_percent) }}
                  </p>
                  <p v-else class="text-muted mt-0.5 text-lg">—</p>
                </div>
              </div>

              <UButton
                v-if="product.cardmarket_url"
                :to="product.cardmarket_url"
                target="_blank"
                external
                color="neutral"
                variant="ghost"
                size="sm"
                icon="i-lucide-external-link"
                class="w-full"
              >
                Voir sur Cardmarket
              </UButton>

              <div class="border-default space-y-3 border-t pt-4">
                <UFormField label="Nom">
                  <UInput v-model="nameDraft" class="w-full" />
                </UFormField>
                <div class="grid grid-cols-2 gap-2">
                  <UFormField label="Type">
                    <USelect
                      v-model="typeDraft"
                      :items="typeOptions"
                      value-key="value"
                      label-key="label"
                      class="w-full"
                    />
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
                <UFormField label="Notes (optionnel)">
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
              </div>

              <UAlert
                v-if="product.article_id"
                color="success"
                variant="subtle"
                icon="i-lucide-tag"
                title="Article créé"
              >
                <template #description>
                  <p class="text-sm">
                    Article
                    <NuxtLink :to="`/articles/${product.article_id}`" class="text-primary underline underline-offset-2">
                      #{{ product.article_id }}
                    </NuxtLink>
                    déjà lié à ce produit.
                  </p>
                </template>
              </UAlert>
            </UCard>

            <UCard class="ring-default ring-1" :ui="{ body: 'p-4 sm:p-6 space-y-4' }">
              <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div class="min-w-0 flex-1 space-y-1">
                  <p class="text-muted text-xs font-medium tracking-wide uppercase">Préparer la vente</p>
                  <p class="text-highlighted text-lg leading-snug font-semibold">Créer un article pour ce produit</p>
                  <p class="text-muted text-sm">
                    Le titre, la description et le prix suggéré sont préremplis. Ajustez puis publiez.
                  </p>
                </div>
                <UButton
                  v-if="!prefill"
                  size="sm"
                  color="primary"
                  variant="solid"
                  icon="i-lucide-sparkles"
                  class="w-full shrink-0 sm:w-auto"
                  :loading="loadingPrefill"
                  @click="onPreparePrefill"
                >
                  Préremplir le formulaire
                </UButton>
                <UButton
                  v-else
                  size="sm"
                  color="neutral"
                  variant="soft"
                  icon="i-lucide-refresh-cw"
                  class="w-full shrink-0 sm:w-auto"
                  :loading="loadingPrefill"
                  @click="onPreparePrefill(true)"
                >
                  Rafraîchir les prix
                </UButton>
              </div>

              <UAlert
                v-if="prefill?.pricing && prefill.pricing.average_price_eur != null"
                color="info"
                variant="subtle"
                icon="i-lucide-trending-up"
                :title="`Prix marché ${prefill.pricing.average_price_eur.toFixed(2)} €`"
                :description="`Suggéré (+${prefill.margin_percent_used}%) : ${prefill.listing_preview.suggested_price?.toFixed(2) ?? '—'} €`"
              />

              <div v-if="prefill">
                <GoupixDexArticleForm
                  ref="formRef"
                  mode="create"
                  :loading="submitting"
                  @submit-create="onSubmitCreate"
                />
              </div>
              <div
                v-else
                class="border-default text-muted flex flex-col items-center gap-3 rounded-xl border border-dashed p-10 text-center text-sm"
              >
                <UIcon name="i-lucide-sparkles" class="text-primary size-8" />
                <p>Cliquez sur « Préremplir le formulaire » pour générer le titre et le prix.</p>
              </div>
            </UCard>
          </div>
        </template>

        <UCard v-else class="ring-default ring-1" :ui="{ body: 'p-10 text-center space-y-3' }">
          <UIcon name="i-lucide-box" class="text-muted mx-auto size-12" />
          <p class="text-highlighted text-base font-medium">Produit introuvable.</p>
          <UButton color="primary" variant="soft" to="/collection/produits" icon="i-lucide-arrow-left">
            Retour aux produits
          </UButton>
        </UCard>
      </div>

      <GoupixDexConfirmModal
        v-model:open="deleteModalOpen"
        title="Retirer ce produit ?"
        description="Ce produit scellé sera supprimé de votre collection. L’action est définitive."
        confirm-label="Retirer"
        confirm-color="error"
        :loading="deleting"
        @confirm="submitDelete"
      />
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { SealedArticlePrefillResponse, SealedProduct, SealedProductType } from '~/composables/useSealed'
import {
  SEALED_TYPE_OPTIONS,
  formatSignedPercent,
  parseEuroAmount,
  sealedProductTypeLabel,
} from '~/utils/sealedProducts'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo('Produit scellé', 'Détail d’un produit scellé de votre collection et préparation de la mise en vente.')

const route = useRoute()
const toast = useToast()
const { getSealed, patchSealed, deleteSealed, prepareArticlePrefill, attachArticle } = useSealed()
const { createArticle, publishArticleToVinted } = useArticles()
const { isDesktopApp } = useDesktopRuntime()

const product = ref<SealedProduct | null>(null)
const loading = ref(true)
const prefill = ref<SealedArticlePrefillResponse | null>(null)
const loadingPrefill = ref(false)
const submitting = ref(false)
const savingDraft = ref(false)
const deleting = ref(false)
const deleteModalOpen = ref(false)
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

const id = computed<number>(() => Number(route.params.id))

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

async function load(): Promise<void> {
  loading.value = true
  try {
    const data = await getSealed(id.value)
    product.value = data
    syncDrafts(data)
  } catch (e) {
    toast.add({ title: 'Produit scellé', description: apiErrorMessage(e), color: 'error' })
    product.value = null
  } finally {
    loading.value = false
  }
}

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
    toast.add({ title: 'Produit mis à jour', color: 'success' })
  } catch (e) {
    toast.add({ title: 'Mise à jour impossible', description: apiErrorMessage(e), color: 'error' })
  } finally {
    savingDraft.value = false
  }
}

function onDelete(): void {
  if (!product.value) {
    return
  }
  deleteModalOpen.value = true
}

async function submitDelete(): Promise<void> {
  if (!product.value) {
    return
  }
  deleting.value = true
  try {
    await deleteSealed(product.value.id)
    deleteModalOpen.value = false
    toast.add({ title: 'Produit retiré', color: 'success' })
    await navigateTo('/collection/produits')
  } catch (e) {
    toast.add({ title: 'Suppression impossible', description: apiErrorMessage(e), color: 'error' })
  } finally {
    deleting.value = false
  }
}

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
      /* ignore — link is best-effort */
    }
    if (isDesktopApp.value && vinted.desktop_local && vinted.stream_path) {
      try {
        await publishArticleToVinted(article.id)
      } catch (e) {
        toast.add({ title: 'Worker Vinted', description: apiErrorMessage(e), color: 'error' })
        await navigateTo('/articles')
        return
      }
      await navigateTo({
        path: '/articles/listing-logs',
        query: { article: String(article.id), progress: 'local' },
      })
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

onMounted(() => {
  void load()
})
</script>
