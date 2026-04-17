<script setup lang="ts">
import type { ScanCardResponse } from '~/composables/useScanCard'
import { syncResultToPrefillSlots, WARDROBE_IMPORT_STORAGE_KEY } from '~/composables/useWardrobeImportPrefill'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  "Création groupée d'articles",
  "Ajoutez plusieurs cartes Pokémon TCG en une session GoupixDex et lancez éventuellement une publication Vinted groupée depuis l'app desktop."
)

type ArticleFormExpose = {
  buildCreateFormData: () => FormData
  applyScanPrefill: (s: ScanCardResponse) => void
  addImageFiles: (files: File[]) => void
  applyWardrobeSlot: (p: import('~/composables/useWardrobeImportPrefill').WardrobeSlotPrefill) => Promise<void>
}

const { createArticle, startVintedBatch, startEbayBatch } = useArticles()
const { scan } = useScanCard()
const toast = useToast()
const { isDesktopApp } = useDesktopRuntime()
const route = useRoute()

let nextSlotId = 1
const formSlots = ref([{ id: 0 }])
const formRefs = ref<(ArticleFormExpose | null)[]>([])
const scanInputKeys = ref<number[]>([0])
const slotHints = ref<string[]>([''])
const slotScanFiles = ref<(File | null)[]>([null])
const slotScanPreviews = ref<(string | null)[]>([null])

const batchVinted = ref(true)
const batchEbay = ref(false)
const wardrobeImportLoading = ref(false)
const submitting = ref(false)
const scanning = ref(false)
const bulkInputKey = ref(0)
const photosPerArticle = ref(2)
const bulkScanInput = ref<HTMLInputElement | null>(null)

function clickBulkScanInput() {
  bulkScanInput.value?.click()
}

function setSlotHint(idx: number, value: string) {
  const next = [...slotHints.value]
  next[idx] = value
  slotHints.value = next
}

function bindFormRef(idx: number, el: unknown) {
  while (formRefs.value.length <= idx) {
    formRefs.value.push(null)
  }
  formRefs.value[idx] = (el as ArticleFormExpose | null) ?? null
}

function addForm() {
  formSlots.value.push({ id: nextSlotId++ })
  scanInputKeys.value.push(0)
  slotHints.value.push('')
  slotScanFiles.value.push(null)
  slotScanPreviews.value.push(null)
}

function removeForm(idx: number) {
  if (formSlots.value.length <= 1) {
    return
  }
  formSlots.value.splice(idx, 1)
  formRefs.value.splice(idx, 1)
  const preview = slotScanPreviews.value[idx]
  if (preview) {
    URL.revokeObjectURL(preview)
  }
  scanInputKeys.value.splice(idx, 1)
  slotHints.value.splice(idx, 1)
  slotScanFiles.value.splice(idx, 1)
  slotScanPreviews.value.splice(idx, 1)
}

async function runScanIntoForm(targetIndex: number, addImage: boolean) {
  const file = slotScanFiles.value[targetIndex]
  const comp = formRefs.value[targetIndex]
  if (!file || !comp?.applyScanPrefill || !comp?.addImageFiles) {
    return
  }

  scanning.value = true
  try {
    const result = await scan(file, 20, slotHints.value[targetIndex] ?? '')
    comp.applyScanPrefill(result)
    if (addImage) {
      comp.addImageFiles([file])
    }
  } catch (e) {
    toast.add({
      title: 'Échec du scan',
      description: apiErrorMessage(e),
      color: 'error'
    })
  } finally {
    scanning.value = false
    scanInputKeys.value[targetIndex] = (scanInputKeys.value[targetIndex] ?? 0) + 1
  }
}

async function onSlotScanFile(idx: number, file: File) {
  slotScanFiles.value[idx] = file
  const prev = slotScanPreviews.value[idx]
  if (prev) {
    URL.revokeObjectURL(prev)
  }
  slotScanPreviews.value[idx] = URL.createObjectURL(file)
  await runScanIntoForm(idx, true)
}

async function onSlotHintBlur(idx: number) {
  if (!slotScanFiles.value[idx]) {
    return
  }
  await runScanIntoForm(idx, false)
}

async function onBulkScanFiles(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  if (!files.length) {
    return
  }
  const chunkSize = Math.max(1, Math.floor(Number(photosPerArticle.value) || 2))
  const chunks: File[][] = []
  for (let i = 0; i < files.length; i += chunkSize) {
    chunks.push(files.slice(i, i + chunkSize))
  }
  while (formSlots.value.length < chunks.length) {
    addForm()
  }

  scanning.value = true
  try {
    for (let idx = 0; idx < chunks.length; idx++) {
      const comp = formRefs.value[idx]
      const chunk = chunks[idx] ?? []
      if (!comp || !chunk.length) {
        continue
      }
      const first = chunk[0]!
      const result = await scan(first, 20, slotHints.value[idx] ?? '')
      comp.applyScanPrefill(result)
      comp.addImageFiles(chunk)
      slotScanFiles.value[idx] = first
      const prev = slotScanPreviews.value[idx]
      if (prev) {
        URL.revokeObjectURL(prev)
      }
      slotScanPreviews.value[idx] = URL.createObjectURL(first)
    }
    toast.add({
      title: 'Préremplissage scan terminé',
      description: `${chunks.length} formulaire(s) alimenté(s) automatiquement.`,
      color: 'success'
    })
  } catch (err) {
    toast.add({
      title: 'Erreur pendant le traitement groupé',
      description: apiErrorMessage(err),
      color: 'error'
    })
  } finally {
    scanning.value = false
    bulkInputKey.value++
  }
}

async function applyWardrobeSessionImport() {
  const raw = sessionStorage.getItem(WARDROBE_IMPORT_STORAGE_KEY)
  if (!raw) {
    return
  }
  sessionStorage.removeItem(WARDROBE_IMPORT_STORAGE_KEY)
  wardrobeImportLoading.value = true
  try {
    const body = JSON.parse(raw) as { result: Record<string, unknown> }
    const slots = syncResultToPrefillSlots(body.result)
    if (!slots.length) {
      toast.add({
        title: 'Aucune annonce à importer',
        description: 'La synchronisation ne contient pas de lignes exploitables.',
        color: 'warning'
      })
      return
    }
    batchVinted.value = false
    for (const p of slotScanPreviews.value) {
      if (p) {
        URL.revokeObjectURL(p)
      }
    }
    formSlots.value = slots.map((_, i) => ({ id: i }))
    nextSlotId = slots.length
    scanInputKeys.value = slots.map(() => 0)
    slotHints.value = slots.map(() => '')
    slotScanFiles.value = slots.map(() => null)
    slotScanPreviews.value = slots.map(() => null)
    formRefs.value = []
    await nextTick()
    await nextTick()
    for (let i = 0; i < slots.length; i++) {
      const comp = formRefs.value[i]
      if (comp?.applyWardrobeSlot) {
        await comp.applyWardrobeSlot(slots[i]!)
      }
    }
    toast.add({
      title: 'Import Vinted',
      description: `${slots.length} fiche(s) préremplie(s). Vérifiez le prix d’achat puis créez les articles.`,
      color: 'success'
    })
  } catch (e) {
    toast.add({
      title: 'Import Vinted',
      description: apiErrorMessage(e),
      color: 'error'
    })
  } finally {
    wardrobeImportLoading.value = false
  }
}

onMounted(async () => {
  if (route.query.from === 'wardrobe') {
    batchVinted.value = false
  }
  await applyWardrobeSessionImport()
})

async function submitAll() {
  const createdIds: number[] = []
  submitting.value = true
  try {
    for (let i = 0; i < formSlots.value.length; i++) {
      const comp = formRefs.value[i]
      if (!comp?.buildCreateFormData) {
        toast.add({
          title: `Formulaire ${i + 1}`,
          description: 'Chargement incomplet — réessayez.',
          color: 'error'
        })
        return
      }
      const fd = comp.buildCreateFormData()
      const title = fd.get('title')?.toString()?.trim()
      const purchase = fd.get('purchase_price')?.toString()?.trim()
      const images = fd.getAll('images') as File[]
      if (!title || !purchase || !images.length) {
        toast.add({
          title: `Article ${i + 1} incomplet`,
          description: 'Titre, prix d\'achat et au moins une image sont requis.',
          color: 'error'
        })
        return
      }
      const { article } = await createArticle(fd)
      createdIds.push(article.id)
    }

    toast.add({
      title: `${createdIds.length} article(s) créé(s)`,
      color: 'success'
    })

    if (batchEbay.value && createdIds.length) {
      try {
        const { queued } = await startEbayBatch(createdIds)
        toast.add({
          title: 'File eBay démarrée',
          description: `${queued} annonce(s) seront publiées successivement sur eBay.`,
          color: 'success'
        })
      } catch (e) {
        toast.add({
          title: 'Création OK — lot eBay non lancé',
          description: apiErrorMessage(e),
          color: 'warning'
        })
      }
    }

    if (isDesktopApp.value && batchVinted.value && createdIds.length) {
      try {
        const { job_id } = await startVintedBatch(createdIds)
        await navigateTo({
          path: '/articles/vinted-logs',
          query: { job: job_id }
        })
      } catch (e) {
        toast.add({
          title: 'Création OK — lot Vinted non lancé',
          description: apiErrorMessage(e),
          color: 'warning'
        })
        await navigateTo('/articles')
      }
    } else {
      await navigateTo('/articles')
    }
  } catch (e) {
    toast.add({
      title: 'Erreur lors de la création',
      description: apiErrorMessage(e),
      color: 'error'
    })
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <UDashboardPanel id="articles-batch-create">
    <template #header>
      <UDashboardNavbar title="Création groupée">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <div class="flex flex-wrap items-center gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              icon="i-lucide-list"
              to="/articles"
            >
              Retour à la liste
            </UButton>
            <UButton
              color="neutral"
              variant="subtle"
              icon="i-lucide-plus"
              @click="addForm"
            >
              Ajouter un formulaire
            </UButton>
          </div>
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
          <div class="relative space-y-3 max-w-3xl">
            <p class="text-xs font-medium uppercase tracking-wide text-primary">
              Création groupée d'articles
            </p>
            <h1 class="text-xl sm:text-2xl font-semibold text-highlighted tracking-tight">
              Préparez plusieurs cartes en une seule passe
            </h1>
            <p class="text-sm sm:text-base text-muted leading-relaxed">
              Remplissez plusieurs fiches, puis lancez la création (et éventuellement la publication Vinted groupée)
              en un seul clic. Idéal après une grosse session de scan ou de tri.
            </p>
          </div>
        </div>

        <UCard class="ring-1 ring-default/60 shadow-sm" :ui="{ body: 'p-4 sm:p-5 space-y-4' }">
          <div class="rounded-xl border border-primary/20 bg-primary/5 p-4 sm:p-5 space-y-4">
            <div class="flex flex-col gap-2">
              <p class="font-medium text-highlighted">
                Ajouter plusieurs photos et préremplir les articles
              </p>
              <p class="text-sm text-muted">
                Importez toutes vos photos d'un coup. GoupixDex les répartit par article, lance les scans et remplit les
                formulaires (champs + images).
              </p>
            </div>
            <div class="grid gap-3 sm:grid-cols-[220px_minmax(0,1fr)] sm:items-end">
              <UFormField label="Photos par article">
                <UInput
                  v-model="photosPerArticle"
                  type="number"
                  min="1"
                  step="1"
                  class="w-full"
                />
              </UFormField>
              <div class="flex flex-wrap items-center gap-2 sm:justify-end">
                <UButton
                  size="sm"
                  color="primary"
                  icon="i-lucide-images"
                  :loading="scanning"
                  @click="clickBulkScanInput"
                >
                  Upload plusieurs images
                </UButton>
              </div>
            </div>
            <input
              :key="bulkInputKey"
              ref="bulkScanInput"
              type="file"
              accept="image/*"
              multiple
              class="hidden"
              @change="onBulkScanFiles"
            >
          </div>

          <p class="text-sm text-muted">
            Les articles sont créés l'un après l'autre. Si vous activez l'option ci-dessous avec l'application desktop,
            une <strong>seule session</strong> Chrome enchaîne les publications Vinted pour limiter les captchas.
          </p>
          <div class="rounded-lg border border-default/80 bg-elevated/60 p-4 space-y-3">
            <UCheckbox
              v-model="batchVinted"
              :disabled="!isDesktopApp || route.query.from === 'wardrobe'"
              label="Lancer la publication Vinted groupée après création (une seule connexion)"
            />
            <p v-if="!isDesktopApp" class="text-sm text-muted">
              Disponible uniquement dans l'app desktop.
              <NuxtLink to="/downloads" class="underline underline-offset-2">
                Télécharger l'app
              </NuxtLink>
            </p>
            <UCheckbox
              v-model="batchEbay"
              label="Lancer la publication eBay en file après création (API, une annonce après l’autre)"
            />
            <p class="text-sm text-muted">
              Nécessite eBay connecté et configuré dans
              <NuxtLink to="/settings/marketplaces" class="underline underline-offset-2">
                Paramètres → Places de marché
              </NuxtLink>
              .
            </p>
          </div>

        </UCard>

        <div class="space-y-6">
          <div
            v-for="(slot, idx) in formSlots"
            :key="slot.id"
            class="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1.1fr)] lg:items-start"
          >
            <UCard class="ring-1 ring-default/60 shadow-sm">
              <template #header>
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <p class="font-medium text-highlighted">
                    Article {{ idx + 1 }} — Détails
                  </p>
                  <UButton
                    v-if="formSlots.length > 1"
                    color="error"
                    variant="ghost"
                    size="xs"
                    icon="i-lucide-trash-2"
                    @click="removeForm(idx)"
                  >
                    Retirer
                  </UButton>
                </div>
              </template>
              <ArticleForm
                :ref="(el) => bindFormRef(idx, el)"
                mode="create"
                :loading="submitting"
                :hide-vinted-option="true"
                :show-submit-button="false"
              />
            </UCard>

            <ScanCardPanel
              :model-value="slotHints[idx] ?? ''"
              @update:model-value="(v: string) => setSlotHint(idx, v)"
              :title="`Article ${idx + 1} — Scanner une carte`"
              subtitle="Scan de carte + prix PokéWallet pour préremplir ce formulaire."
              :preview-url="slotScanPreviews[idx]"
              :scanning="scanning"
              :input-key="scanInputKeys[idx]"
              :hint-disabled="!slotScanFiles[idx]"
              hint-label="Indice pour le scan (optionnel)"
              hint-description="Au blur du champ, un nouveau scan est relancé sur la photo courante."
              hint-placeholder="Ex. Pikachu SV5a 063/065, ou Gloupti M1L…"
              @file-selected="(file) => onSlotScanFile(idx, file)"
              @hint-blur="onSlotHintBlur(idx)"
            />
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-3">
          <UButton
            color="primary"
            size="lg"
            icon="i-lucide-upload-cloud"
            :loading="submitting"
            @click="submitAll"
          >
            Créer {{ formSlots.length }} article(s)
            <span v-if="batchVinted && isDesktopApp"> et lancer Vinted</span>
            <span v-if="batchEbay"> et eBay</span>
          </UButton>
          <UButton
            color="neutral"
            variant="soft"
            icon="i-lucide-plus"
            @click="addForm"
          >
            Ajouter un formulaire
          </UButton>
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>
