<script setup lang="ts">
import type { ScanCardResponse } from '~/composables/useScanCard'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Nouvel article',
  'Créez une fiche article dans GoupixDex : scan, photos, prix Cardmarket, description et option de publication Vinted (application desktop).'
)

const formRef = ref<{
  applyScanPrefill: (s: ScanCardResponse) => void
  addImageFiles: (files: File[]) => void
} | null>(null)

const { scan } = useScanCard()
const { createArticle, publishArticleToVinted } = useArticles()
const { getSettings } = useSettings()
const toast = useToast()
const { isDesktopApp } = useDesktopRuntime()

const scanning = ref(false)
const lastScanFile = ref<File | null>(null)
const scanPreviewUrl = ref<string | null>(null)
const submitting = ref(false)
const vintedSubmit = ref(false)
const scanInputKey = ref(0)
/** Texte optionnel pour aider le scan de carte (nom, set, code, n°…). */
const scanOcrHint = ref('')

async function runScan(addImage: boolean) {
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
    formRef.value?.applyScanPrefill(res)
    if (addImage) {
      formRef.value?.addImageFiles([file])
    }
    toast.add({ title: 'Carte scannée — vérifiez les champs', color: 'success' })
  } catch (err) {
    toast.add({
      title: 'Échec du scan',
      description: apiErrorMessage(err),
      color: 'error'
    })
  } finally {
    scanning.value = false
    scanInputKey.value++
  }
}

async function onScanFile(file: File) {
  if (scanPreviewUrl.value) {
    URL.revokeObjectURL(scanPreviewUrl.value)
  }
  lastScanFile.value = file
  scanPreviewUrl.value = URL.createObjectURL(file)
  await runScan(true)
}

async function onOcrHintBlur() {
  if (!lastScanFile.value) return
  await runScan(false)
}

async function onSubmitCreate(fd: FormData) {
  if (!isDesktopApp.value) {
    fd.set('publish_to_vinted', 'false')
  }
  vintedSubmit.value = fd.get('publish_to_vinted') === 'true'
  submitting.value = true
  try {
    const { article, vinted, ebay } = await createArticle(fd)

    function notifyEbayOutcome() {
      if (ebay?.status === 'running') {
        toast.add({
          title: 'Publication eBay lancée',
          description: 'La mise en ligne se fait en arrière-plan (vérifiez votre vendeur eBay).',
          color: 'success'
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
            'Les photos doivent être enregistrées et accessibles en ligne pour publier sur eBay — réessayez après upload des images.'
        }
        toast.add({
          title: 'Article créé — eBay ignoré',
          description: ebayMsg[ebay.detail] ?? ebay.detail,
          color: 'warning'
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
          color: 'error'
        })
        await navigateTo('/articles')
        return
      }
      notifyEbayOutcome()
      await navigateTo({
        path: '/articles/listing-logs',
        query: { article: String(article.id), progress: 'local' }
      })
      return
    }

    if (vinted.status === 'running' && vinted.stream_path) {
      notifyEbayOutcome()
      await navigateTo({
        path: '/articles/listing-logs',
        query: { article: String(article.id) }
      })
      return
    }

    const ebayNotified = notifyEbayOutcome()

    if (ebay?.status === 'running' && ebay?.stream_path) {
      await navigateTo({
        path: '/articles/listing-logs',
        query: { article: String(article.id) }
      })
      return
    }

    if (vintedSubmit.value) {
      if (vinted.published) {
        toast.add({
          title: 'Article créé et publié sur Vinted',
          color: 'success'
        })
      } else {
        toast.add({
          title: 'Article créé',
          description:
            vinted.detail === 'missing_vinted_credentials'
              ? "Identifiants Vinted manquants (profil utilisateur ou variables d'environnement)."
              : vinted.detail === 'vinted_disabled'
                ? 'Vinted est désactivé dans Paramètres → Places de marché.'
                : (typeof vinted.detail === 'string' ? vinted.detail : 'Publication Vinted non confirmée.'),
          color: 'warning'
        })
      }
    } else if (!ebayNotified) {
      toast.add({ title: 'Article créé', color: 'success' })
    }
    await navigateTo('/articles')
  } catch (err) {
    toast.add({
      title: 'Création impossible',
      description: apiErrorMessage(err),
      color: 'error'
    })
  } finally {
    submitting.value = false
    vintedSubmit.value = false
  }
}
</script>

<template>
  <UDashboardPanel id="article-create">
    <template #header>
      <UDashboardNavbar title="Nouvel article">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton to="/articles" color="neutral" variant="ghost" icon="i-lucide-list">
            Retour à la liste
          </UButton>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="w-full px-4 sm:px-6 py-6 sm:py-8 space-y-6 sm:space-y-8">
        <!-- Bandeau contexte -->
        <div
          class="relative overflow-hidden rounded-2xl border border-default bg-gradient-to-br from-primary/10 via-elevated/60 to-primary/5 px-5 py-5 sm:px-7 sm:py-7"
        >
          <div class="absolute -right-16 -top-16 size-48 rounded-full bg-primary/10 blur-3xl pointer-events-none" />
          <div class="absolute -bottom-24 -left-10 size-44 rounded-full bg-primary/5 blur-3xl pointer-events-none" />
          <div class="relative flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div class="space-y-2 max-w-2xl">
              <p class="text-xs font-medium uppercase tracking-wide text-primary">
                Création d'article
              </p>
              <h1 class="text-xl sm:text-2xl font-semibold text-highlighted tracking-tight">
                Scanner une carte et préparer sa fiche de vente
              </h1>
              <p class="text-sm sm:text-base text-muted leading-relaxed">
                Importez une photo, laissez GoupixDex lire le set, le numéro et les prix de référence,
                puis ajustez le titre, la description et les options Vinted avant publication.
              </p>
            </div>
            <div class="flex flex-row lg:flex-col gap-2 lg:items-end shrink-0">
              <UButton
                to="/articles/batch-create"
                size="sm"
                color="neutral"
                variant="soft"
                icon="i-lucide-layers"
              >
                Création groupée
              </UButton>
            </div>
          </div>
        </div>

        <div class="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1.1fr)] lg:items-start">
          <!-- Bloc formulaire principal (gauche) -->
          <UCard class="ring-1 ring-default/60 shadow-sm order-2 lg:order-1">
            <template #header>
              <div class="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                <p class="font-medium text-highlighted">
                  Détails de l'article
                </p>
                <p class="text-xs text-muted max-w-xs">
                  Vérifiez toujours le set, le numéro et les prix suggérés avant de publier sur Vinted.
                </p>
              </div>
            </template>
            <ArticleForm
              ref="formRef"
              mode="create"
              :loading="submitting"
              :loading-hint="
                submitting && vintedSubmit
                  ? 'Création de l\'article… puis ouverture du journal Vinted.'
                  : undefined
              "
              @submit-create="onSubmitCreate"
            />
          </UCard>

          <!-- Bloc scan (droite) -->
          <ScanCardPanel
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
