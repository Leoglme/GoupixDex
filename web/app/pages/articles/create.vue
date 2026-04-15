<script setup lang="ts">
import type { ScanCardResponse } from '~/composables/useScanCard'

definePageMeta({ middleware: 'auth' })

const formRef = ref<{
  applyScanPrefill: (s: ScanCardResponse) => void
  addImageFiles: (files: File[]) => void
} | null>(null)

const { scan } = useScanCard()
const { createArticle } = useArticles()
const { getSettings } = useSettings()
const toast = useToast()

const scanning = ref(false)
const submitting = ref(false)
const vintedSubmit = ref(false)
const scanInputKey = ref(0)

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
    const res = await scan(file, margin)
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
  vintedSubmit.value = fd.get('publish_to_vinted') === 'true'
  submitting.value = true
  try {
    const { article, vinted } = await createArticle(fd)

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
