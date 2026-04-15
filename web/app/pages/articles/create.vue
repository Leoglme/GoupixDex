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
const submitting = ref(false)
const vintedSubmit = ref(false)
const scanInputKey = ref(0)
/** Texte optionnel pour aider l’OCR (nom, set, code, n°…). */
const scanOcrHint = ref('')

async function onScanFile(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) {
    return
  }
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
    formRef.value?.addImageFiles([file])
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

async function onSubmitCreate(fd: FormData) {
  if (!isDesktopApp.value) {
    fd.set('publish_to_vinted', 'false')
  }
  vintedSubmit.value = fd.get('publish_to_vinted') === 'true'
  submitting.value = true
  try {
    const { article, vinted } = await createArticle(fd)

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
      await navigateTo({
        path: '/articles/vinted-logs',
        query: { article: String(article.id) }
      })
      return
    }

    if (vinted.status === 'running' && vinted.stream_path) {
      await navigateTo({
        path: '/articles/vinted-logs',
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
              : (typeof vinted.detail === 'string' ? vinted.detail : 'Publication Vinted non confirmée.'),
          color: 'warning'
        })
      }
    } else {
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
          <UButton to="/articles" color="neutral" variant="ghost">
            Retour à la liste
          </UButton>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="p-4 sm:p-6 max-w-3xl space-y-8">
        <UCard>
          <template #header>
            <div>
              <p class="font-medium text-highlighted">
                Scanner une carte
              </p>
              <p class="text-sm text-muted">
                OCR + prix PokéWallet (Cardmarket / TCGPlayer) pour préremplir le formulaire.
              </p>
            </div>
          </template>
          <div class="space-y-4">
            <div class="flex flex-wrap items-center gap-3">
              <UInput
                :key="scanInputKey"
                type="file"
                accept="image/*"
                :disabled="scanning"
                :ui="{
                  base: 'cursor-pointer file:cursor-pointer disabled:cursor-not-allowed'
                }"
                @change="onScanFile"
              />
              <UIcon
                v-if="scanning"
                name="i-lucide-loader-2"
                class="size-5 animate-spin text-primary"
              />
            </div>
            <UFormField
              label="Indice pour l’OCR (optionnel)"
              description="Si la photo est floue ou difficile, indiquez par ex. le Pokémon, l’extension, le code set (SV5a…) ou le n° de carte pour aider la reconnaissance."
              class="w-full max-w-xl"
            >
              <UInput
                v-model="scanOcrHint"
                placeholder="Ex. Pikachu SV5a 063/065, ou Gloupti M1L…"
                :disabled="scanning"
                class="mt-4 w-full sm:mt-5"
              />
            </UFormField>
          </div>
        </UCard>

        <UCard>
          <template #header>
            <p class="font-medium text-highlighted">
              Détails de l'article
            </p>
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
      </div>
    </template>
  </UDashboardPanel>
</template>
