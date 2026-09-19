<template>
  <UDashboardPanel id="article-create">
    <template #header>
      <UDashboardNavbar>
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #title>
          <span class="app-label flex items-center gap-1.5 !text-[0.65rem]">
            <UIcon name="i-lucide-flame" class="h-3 w-3 text-(--app-accent)" />
            Vente
          </span>
        </template>
        <template #right>
          <UButton to="/articles/stock" color="neutral" variant="ghost" icon="i-lucide-package"> Mes articles </UButton>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="w-full space-y-3 px-2 py-2.5 sm:space-y-4 sm:px-4 sm:py-4">
        <GoupixDexPageHeader
          title="Nouvel article"
          description="Importez une photo, laissez GoupixDex lire le set, le numéro et les prix de référence, puis ajustez la fiche avant publication."
        >
          <template #actions>
            <UButton to="/articles/batch-create" color="neutral" variant="subtle" icon="i-lucide-layers">
              Création groupée
            </UButton>
          </template>
        </GoupixDexPageHeader>

        <div class="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1.1fr)] lg:items-start">
          <!-- Bloc formulaire principal (gauche) -->
          <UCard class="ring-default order-2 ring-1 lg:order-1">
            <template #header>
              <div class="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                <p class="text-highlighted font-medium">Détails de l'article</p>
                <p class="text-muted max-w-xs text-xs">
                  Vérifiez toujours le set, le numéro et les prix suggérés avant de publier sur Vinted.
                </p>
              </div>
            </template>
            <GoupixDexArticleForm
              ref="formRef"
              mode="create"
              :loading="submitting"
              :loading-hint="
                submitting && vintedSubmit ? 'Création de l\'article… puis ouverture du journal Vinted.' : undefined
              "
              @submit-create="onSubmitCreate"
            />
          </UCard>

          <!-- Bloc scan (droite) -->
          <GoupixDexScanCardPanel
            v-model="scanOcrHint"
            class="order-1 lg:order-2"
            :preview-url="scanPreviewUrl"
            :scanning="scanning"
            :input-key="scanInputKey"
            :hint-disabled="!lastScanFile"
            hint-label="Indice pour le scan (optionnel)"
            hint-description="Si la photo est floue ou difficile, indiquez par ex. le Pokémon, l'extension, le code set (SV5a…) ou le n° de carte pour aider la reconnaissance."
            hint-placeholder="Ex. Pikachu SV5a 063/065, ou Gloupti M1L…"
            @file-selected="onScanFile"
            @hint-blur="onOcrHintBlur"
          />
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { Ref } from 'vue'
import type { ScanCardResponse } from '~/composables/useScanCard'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Nouvel article',
  'Créez une fiche article dans GoupixDex : scan, photos, prix Cardmarket, description et option de publication Vinted (application desktop).',
)

const { scan } = useScanCard()
const { createArticle, publishArticleToVinted } = useArticles()
const { getSettings } = useSettings()
const toast = useToast()
const { isDesktopApp } = useDesktopRuntime()

const formRef: Ref<{
  applyScanPrefill: (s: ScanCardResponse) => Promise<void>
  addImageFiles: (files: File[]) => void
  applyEbayPrefill: (p: {
    title?: string
    description?: string
    pokemonName?: string
    setCode?: string
    cardNumber?: string
    condition?: string
    purchasePrice?: string
    sellPrice?: string
    imageUrl?: string | null
  }) => Promise<void>
} | null> = ref<{
  applyScanPrefill: (s: ScanCardResponse) => Promise<void>
  addImageFiles: (files: File[]) => void
  applyEbayPrefill: (p: {
    title?: string
    description?: string
    pokemonName?: string
    setCode?: string
    cardNumber?: string
    condition?: string
    purchasePrice?: string
    sellPrice?: string
    imageUrl?: string | null
  }) => Promise<void>
} | null>(null)

const route = useRoute()

const scanning: Ref<boolean> = ref(false)
const lastScanFile: Ref<File | null> = ref(null)
const scanPreviewUrl: Ref<string | null> = ref(null)
const submitting: Ref<boolean> = ref(false)
const vintedSubmit: Ref<boolean> = ref(false)
const scanInputKey: Ref<number> = ref(0)
const scanOcrHint: Ref<string> = ref('')

function qs(key: string): string | undefined {
  const raw = route.query[key]
  if (Array.isArray(raw)) {
    return raw[0] ?? undefined
  }
  return typeof raw === 'string' ? raw : undefined
}

async function runScan(addImage: boolean): Promise<void> {
  const file = lastScanFile.value
  if (!file) return

  scanning.value = true
  try {
    let margin = 20
    try {
      const s = await getSettings()
      margin = s.margin_percent
    } catch {
      /* ignore */
    }
    const res = await scan(file, margin, scanOcrHint.value)
    await formRef.value?.applyScanPrefill(res)
    if (addImage) {
      formRef.value?.addImageFiles([file])
    }
    toast.add({ title: 'Carte scannée — vérifiez les champs', color: 'success' })
  } catch (err) {
    toast.add({
      title: 'Échec du scan',
      description: apiErrorMessage(err),
      color: 'error',
    })
  } finally {
    scanning.value = false
    scanInputKey.value++
  }
}

async function onScanFile(file: File): Promise<void> {
  if (scanPreviewUrl.value) {
    URL.revokeObjectURL(scanPreviewUrl.value)
  }
  lastScanFile.value = file
  scanPreviewUrl.value = URL.createObjectURL(file)
  await runScan(true)
}

async function onOcrHintBlur(): Promise<void> {
  if (!lastScanFile.value) return
  await runScan(false)
}

async function onSubmitCreate(fd: FormData): Promise<void> {
  if (!isDesktopApp.value) {
    fd.set('publish_to_vinted', 'false')
  }
  vintedSubmit.value = fd.get('publish_to_vinted') === 'true'
  submitting.value = true
  try {
    const { article, vinted, ebay } = await createArticle(fd)

    function notifyEbayOutcome(): boolean {
      if (ebay?.status === 'running') {
        toast.add({
          title: 'Publication eBay lancée',
          description: 'La mise en ligne se fait en arrière-plan (vérifiez votre vendeur eBay).',
          color: 'success',
        })
        return true
      }
      if (ebay?.skipped && ebay?.detail) {
        const ebayMsg: Record<string, string> = {
          ebay_disabled: 'eBay est désactivé dans les paramètres.',
          ebay_listing_config_incomplete:
            'Terminez la configuration eBay dans Paramètres → Places de marché (adresse et règles).',
          ebay_not_connected: 'Connectez votre compte eBay dans Paramètres → Places de marché.',
          ebay_requires_https_images:
            'Les photos doivent être enregistrées et accessibles en ligne pour publier sur eBay — réessayez après upload des images.',
        }
        toast.add({
          title: 'Article créé — eBay ignoré',
          description: ebayMsg[ebay.detail] ?? ebay.detail,
          color: 'warning',
        })
        return true
      }
      return false
    }

    if (isDesktopApp.value && vinted.desktop_local && vinted.stream_path) {
      try {
        await publishArticleToVinted(article.id)
      } catch (err) {
        toast.add({
          title: 'Worker Vinted local',
          description: apiErrorMessage(err),
          color: 'error',
        })
        await navigateTo('/articles/stock')
        return
      }
      notifyEbayOutcome()
      await navigateTo({
        path: '/articles/listing-logs',
        query: { article: String(article.id), progress: 'local' },
      })
      return
    }

    if (vinted.status === 'running' && vinted.stream_path) {
      notifyEbayOutcome()
      await navigateTo({
        path: '/articles/listing-logs',
        query: { article: String(article.id) },
      })
      return
    }

    const ebayNotified = notifyEbayOutcome()

    if (ebay?.status === 'running' && ebay?.stream_path) {
      await navigateTo({
        path: '/articles/listing-logs',
        query: { article: String(article.id) },
      })
      return
    }

    if (vintedSubmit.value) {
      if (vinted.published) {
        toast.add({
          title: 'Article créé et publié sur Vinted',
          color: 'success',
        })
      } else {
        toast.add({
          title: 'Article créé',
          description:
            vinted.detail === 'missing_vinted_credentials'
              ? "Identifiants Vinted manquants (profil utilisateur ou variables d'environnement)."
              : vinted.detail === 'vinted_disabled'
                ? 'Vinted est désactivé dans Paramètres → Places de marché.'
                : typeof vinted.detail === 'string'
                  ? vinted.detail
                  : 'Publication Vinted non confirmée.',
          color: 'warning',
        })
      }
    } else if (!ebayNotified) {
      toast.add({ title: 'Article créé', color: 'success' })
    }
    await navigateTo('/articles/stock')
  } catch (err) {
    toast.add({
      title: 'Création impossible',
      description: apiErrorMessage(err),
      color: 'error',
    })
  } finally {
    submitting.value = false
    vintedSubmit.value = false
  }
}

onMounted((): void => {
  void (async (): Promise<void> => {
    const title = qs('title')
    const purchasePrice = qs('purchase_price')
    if (!title && !purchasePrice) {
      return
    }
    await nextTick()
    try {
      await formRef.value?.applyEbayPrefill({
        title,
        description: qs('description'),
        pokemonName: qs('pokemon_name'),
        setCode: qs('set_code'),
        cardNumber: qs('card_number'),
        condition: qs('condition'),
        purchasePrice,
        sellPrice: qs('sell_price'),
        imageUrl: qs('image_url') ?? null,
      })
      toast.add({
        title: 'Formulaire prérempli depuis eBay',
        description: 'Vérifiez le Pokémon, le set, le numéro et le prix avant de valider.',
        color: 'success',
      })
    } catch {
      /* best effort */
    }
  })()
})
</script>
