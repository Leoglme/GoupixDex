<template>
  <UDashboardPanel id="binder-editor">
    <template #header>
      <UDashboardNavbar>
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #title>
          <span class="app-label flex items-center gap-1.5 !text-[0.65rem]">
            <UIcon name="i-lucide-palette" class="h-3 w-3 text-(--app-accent)" />
            Personnalisation
          </span>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div v-if="loading" class="flex justify-center py-20">
        <UIcon name="i-lucide-loader-2" class="size-10 animate-spin text-(--app-accent)" />
      </div>

      <div v-else-if="loadError" class="app-dashboard-page space-y-4">
        <NuxtLink
          :to="`/classeurs/${binderId}`"
          class="inline-flex w-fit items-center gap-1 text-sm font-medium text-(--app-accent) underline-offset-4 transition hover:underline"
        >
          <UIcon name="i-lucide-arrow-left" class="size-4 shrink-0" aria-hidden />
          Retour
        </NuxtLink>
        <UAlert color="error" title="Impossible de charger l'éditeur" description="Réessaie ou reviens au classeur." />
        <UButton color="neutral" variant="outline" @click="load">Réessayer</UButton>
      </div>

      <div v-else-if="editorReady" class="app-dashboard-page">
        <GoupixDexBinderEditor
          :binder-id="binderId"
          :name="binderName"
          :initial-style="initialStyle"
          :initial-color="initialColor"
          :initial-cover-ids="initialCoverIds"
          :initial-grid="initialGrid"
          :initial-design="initialDesign"
          :initial-layout="initialLayout"
          :initial-urls="initialUrls"
          :cards="editorCards"
          :sets="editorSets"
          @saved="onSaved"
        />
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { EditorSet } from '~/components/binder/GoupixDexBinderEditor.vue'
import type { EditorCard } from '~/components/binder/GoupixDexBinderEditorCardPicker.vue'
import type { BinderDetail } from '~/types/binders'
import { coverLayout, coverStoragePaths } from '~/utils/binder/binder-cover'
import { binderDesign } from '~/utils/binder/binder-design'
import { apiErrorMessage } from '~/composables/useApiError'

definePageMeta({ middleware: 'auth' })

const route = useRoute()
const router = useRouter()
const { getBinder, resolveCoverUrls } = useBinders()
const { browseCatalog, browseCatalogFromApi } = useCardCatalog()
const toast = useToast()

const binderId = computed(() => Number(route.params.id))
const loading = ref(true)
const editorReady = ref(false)
const loadError = ref(false)

const binderName = ref('')
const initialStyle = ref<string | null>(null)
const initialColor = ref<string | null>(null)
const initialCoverIds = ref<number[]>([])
const initialGrid = ref<string | null>(null)
const initialDesign = ref(binderDesign(null))
const initialLayout = ref(coverLayout(null))
const initialUrls = ref<Record<string, string>>({})
const editorCards = ref<EditorCard[]>([])
const editorSets = ref<EditorSet[]>([])

function buildEditorCards(binder: BinderDetail): EditorCard[] {
  const seen = new Set<number>()
  const out: EditorCard[] = []
  for (const item of binder.items) {
    if (seen.has(item.collection_card_id)) continue
    if (!item.image_url?.trim()) continue
    seen.add(item.collection_card_id)
    out.push({
      id: String(item.collection_card_id),
      name: item.card_name,
      image_url: item.image_url,
    })
  }
  return out
}

function flattenCatalogSets(browse: {
  series?: {
    id: string
    name: string
    display_name?: string
    sets?: { id: string; name: string; display_name?: string; logo?: string; symbol?: string }[]
  }[]
}): EditorSet[] {
  const sets: EditorSet[] = []
  for (const serie of browse.series ?? []) {
    for (const set of serie.sets ?? []) {
      sets.push({
        id: set.id,
        name: set.display_name ?? set.name,
        serie: serie.display_name ?? serie.name,
        logo: set.logo ?? null,
        symbol: set.symbol ?? null,
      })
    }
  }
  return sets
}

async function loadCatalogSets(): Promise<EditorSet[]> {
  try {
    return flattenCatalogSets(await browseCatalog('fr'))
  } catch {
    try {
      return flattenCatalogSets(await browseCatalogFromApi('fr'))
    } catch {
      return []
    }
  }
}

async function load(): Promise<void> {
  loading.value = true
  editorReady.value = false
  loadError.value = false
  if (!Number.isFinite(binderId.value)) {
    loading.value = false
    loadError.value = true
    return
  }
  try {
    const binder = await getBinder(binderId.value)

    binderName.value = binder.name
    initialStyle.value = binder.style
    initialColor.value = binder.color
    initialCoverIds.value = [...(binder.cover_collection_card_ids ?? [])]
    initialGrid.value = binder.page_grid
    initialDesign.value = binderDesign(binder.design)
    initialLayout.value = coverLayout(binder.cover)
    editorCards.value = buildEditorCards(binder)
    editorSets.value = await loadCatalogSets()

    const paths = coverStoragePaths(initialLayout.value)
    let urls: Record<string, string> = { ...(binder.cover_urls ?? {}) }
    const missing = paths.filter((p) => !urls[p])
    if (missing.length) {
      try {
        urls = { ...urls, ...(await resolveCoverUrls(binder.id, missing)) }
      } catch {
        /* images custom optionnelles */
      }
    }
    initialUrls.value = urls

    editorReady.value = true
  } catch (e) {
    loadError.value = true
    toast.add({ title: 'Classeur introuvable', description: apiErrorMessage(e), color: 'error' })
  } finally {
    loading.value = false
  }
}

function onSaved(): void {
  void router.push(`/classeurs/${binderId.value}`)
}

watch(
  () => route.params.id,
  () => {
    void load()
  },
)

onMounted(() => {
  void load()
})
</script>
