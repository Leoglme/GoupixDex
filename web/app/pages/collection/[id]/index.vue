<template>
  <UDashboardPanel id="collection-card-page">
    <template #header>
      <UDashboardNavbar title="Carte de la collection">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton to="/collection" color="neutral" variant="ghost" icon="i-lucide-arrow-left"> Ma collection </UButton>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="w-full space-y-5 px-4 py-5 sm:space-y-6 sm:px-6 sm:py-6">
        <div v-if="loading" class="flex items-center justify-center py-20">
          <UIcon name="i-lucide-loader-2" class="text-primary size-10 animate-spin" />
        </div>

        <template v-else-if="card">
          <div class="grid gap-4 lg:grid-cols-[minmax(0,360px)_1fr] lg:items-start lg:gap-6">
            <UCard class="ring-default/60 shadow-sm ring-1" :ui="{ body: 'p-4 sm:p-5 space-y-4' }">
              <div class="bg-muted/20 mx-auto aspect-[63/88] w-full max-w-[300px] overflow-hidden rounded-xl">
                <img
                  v-if="card.image_url"
                  :src="card.image_url"
                  :alt="card.display_name"
                  class="h-full w-full object-contain"
                  referrerpolicy="no-referrer"
                  decoding="async"
                />
                <div v-else class="flex h-full items-center justify-center">
                  <UIcon name="i-lucide-image-off" class="text-muted size-10" />
                </div>
              </div>

              <div class="space-y-1.5">
                <p class="text-highlighted text-lg leading-snug font-semibold">{{ card.display_name }}</p>
                <p class="text-muted text-sm">{{ card.set_name || card.tcgdex_set_id }} · #{{ card.card_number }}</p>
                <div class="flex flex-wrap gap-1.5 pt-1">
                  <UBadge color="primary" variant="subtle" size="sm">
                    {{ languageLabel(card.language) }}
                  </UBadge>
                  <UBadge v-if="card.set_code" color="neutral" variant="subtle" size="sm">
                    Code {{ card.set_code }}
                  </UBadge>
                  <UBadge v-if="card.rarity" color="warning" variant="subtle" size="sm">
                    {{ card.rarity }}
                  </UBadge>
                  <UBadge color="neutral" variant="soft" size="sm">×{{ card.quantity }}</UBadge>
                </div>
              </div>

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
              <UFormField label="Notes (optionnel)">
                <UTextarea v-model="notesDraft" :rows="3" class="w-full" />
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
                  Retirer de ma collection
                </UButton>
              </div>

              <UAlert v-if="card.article_id" color="success" variant="subtle" icon="i-lucide-tag" title="Article créé">
                <template #description>
                  <p class="text-sm">
                    Article
                    <NuxtLink :to="`/articles/${card.article_id}`" class="text-primary underline underline-offset-2">
                      #{{ card.article_id }}
                    </NuxtLink>
                    déjà lié à cette carte de collection.
                  </p>
                </template>
              </UAlert>
            </UCard>

            <UCard class="ring-default/60 shadow-sm ring-1" :ui="{ body: 'p-4 sm:p-6 space-y-4' }">
              <div class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div class="space-y-1">
                  <p class="text-muted text-xs font-medium tracking-wide uppercase">Préparer la vente</p>
                  <p class="text-highlighted text-lg leading-snug font-semibold">
                    Créer un article à partir de cette carte
                  </p>
                  <p class="text-muted text-sm">
                    Les infos de la carte sont préremplies. Ajustez prix, état et marketplaces puis publiez.
                  </p>
                </div>
                <UButton
                  v-if="!prefill"
                  color="primary"
                  variant="solid"
                  icon="i-lucide-sparkles"
                  :loading="loadingPrefill"
                  @click="onPreparePrefill"
                >
                  Préremplir le formulaire
                </UButton>
                <UButton
                  v-else
                  color="neutral"
                  variant="soft"
                  icon="i-lucide-refresh-cw"
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
                :title="`Prix moyen marché ${prefill.pricing.average_price_eur.toFixed(2)} €`"
                :description="`Suggéré (+${prefill.margin_percent_used}%) : ${prefill.listing_preview.suggested_price?.toFixed(2) ?? '—'} €`"
              />

              <UAlert
                v-else-if="prefill?.pricing?.error"
                color="warning"
                variant="subtle"
                icon="i-lucide-alert-triangle"
                title="Pas de prix marché"
                :description="prefill.pricing.error"
              />

              <div v-if="prefill">
                <ArticleForm ref="formRef" mode="create" :loading="submitting" @submit-create="onSubmitCreate" />
              </div>
              <div
                v-else
                class="border-default text-muted flex flex-col items-center gap-3 rounded-xl border border-dashed p-10 text-center text-sm"
              >
                <UIcon name="i-lucide-sparkles" class="text-primary size-8" />
                <p>Cliquez sur « Préremplir le formulaire » pour récupérer les prix et générer le titre.</p>
              </div>
            </UCard>
          </div>
        </template>

        <UCard v-else class="ring-default/60 shadow-sm ring-1" :ui="{ body: 'p-10 text-center space-y-3' }">
          <UIcon name="i-lucide-album-x" class="text-muted mx-auto size-12" />
          <p class="text-highlighted text-base font-medium">Carte introuvable dans la collection.</p>
          <UButton color="primary" variant="soft" to="/collection" icon="i-lucide-arrow-left">
            Retour à ma collection
          </UButton>
        </UCard>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { CollectionArticlePrefillResponse, CollectionCard } from '~/composables/useCollection'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Carte de collection',
  'Détail d’une carte de votre collection Pokémon et préparation de la mise en vente.',
)

const route = useRoute()
const toast = useToast()
const { getCollectionCard, patchCollectionCard, deleteCollectionCard, prepareArticlePrefill, attachArticle } =
  useCollection()
const { createArticle, publishArticleToVinted } = useArticles()
const { isDesktopApp } = useDesktopRuntime()

const card: Ref<CollectionCard | null> = ref(null)
const loading = ref(true)
const prefill: Ref<CollectionArticlePrefillResponse | null> = ref(null)
const loadingPrefill = ref(false)
const submitting = ref(false)
const savingDraft = ref(false)
const deleting = ref(false)
const formRef = ref<{
  applyCatalogPrefill: (p: CollectionArticlePrefillResponse) => Promise<void>
  buildCreateFormData: () => FormData
} | null>(null)

const quantityDraft = ref(1)
const languageDraft = ref<string>('fr')
const notesDraft = ref('')

const languageItems = [
  { label: 'Français', value: 'fr' },
  { label: 'Anglais', value: 'en' },
  { label: 'Japonais', value: 'ja' },
]

const id = computed(() => Number(route.params.id))

const isDirty = computed(() => {
  if (!card.value) {
    return false
  }
  return (
    quantityDraft.value !== card.value.quantity ||
    languageDraft.value !== card.value.language ||
    (notesDraft.value || '') !== (card.value.notes || '')
  )
})

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

function syncDrafts(c: CollectionCard): void {
  quantityDraft.value = c.quantity
  languageDraft.value = c.language
  notesDraft.value = c.notes ?? ''
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const data = await getCollectionCard(id.value)
    card.value = data
    syncDrafts(data)
  } catch (e) {
    toast.add({ title: 'Carte de collection', description: apiErrorMessage(e), color: 'error' })
    card.value = null
  } finally {
    loading.value = false
  }
}

async function onSaveDraft(): Promise<void> {
  if (!card.value) {
    return
  }
  savingDraft.value = true
  try {
    const updated = await patchCollectionCard(card.value.id, {
      quantity: quantityDraft.value,
      language: languageDraft.value,
      notes: notesDraft.value,
    })
    card.value = updated
    syncDrafts(updated)
    toast.add({ title: 'Carte mise à jour', color: 'success' })
  } catch (e) {
    toast.add({ title: 'Mise à jour impossible', description: apiErrorMessage(e), color: 'error' })
  } finally {
    savingDraft.value = false
  }
}

async function onDelete(): Promise<void> {
  if (!card.value) {
    return
  }
  if (!window.confirm('Retirer cette carte de votre collection ?')) {
    return
  }
  deleting.value = true
  try {
    await deleteCollectionCard(card.value.id)
    toast.add({ title: 'Carte retirée de la collection', color: 'success' })
    await navigateTo('/collection')
  } catch (e) {
    toast.add({ title: 'Suppression impossible', description: apiErrorMessage(e), color: 'error' })
  } finally {
    deleting.value = false
  }
}

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
      /* ignore — link is best-effort */
    }
    if (isDesktopApp.value && vinted.desktop_local && vinted.stream_path) {
      try {
        await publishArticleToVinted(article.id)
      } catch (e) {
        toast.add({ title: 'Worker Vinted', description: apiErrorMessage(e), color: 'error' })
        await navigateTo('/articles/stock')
        return
      }
      await navigateTo({
        path: '/articles/listing-logs',
        query: { article: String(article.id), progress: 'local' },
      })
      return
    }
    toast.add({ title: 'Article créé depuis la collection', color: 'success' })
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
