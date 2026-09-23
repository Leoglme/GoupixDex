<template>
  <UDashboardPanel id="collection-catalog-set-page">
    <template #header>
      <UDashboardNavbar>
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #title>
          <span class="app-label flex items-center gap-1.5 !text-[0.65rem]">
            <UIcon name="i-lucide-flame" class="h-3 w-3 text-(--app-accent)" />
            Collection
          </span>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="app-dashboard-page w-full space-y-4 sm:space-y-5">
        <GoupixDexBackLink :to="backToCatalogLink" />

        <div v-if="setLoading" class="flex items-center justify-center py-24">
          <UIcon name="i-lucide-loader-2" class="text-primary size-10 animate-spin" />
        </div>

        <template v-else-if="setDetail">
          <div class="flex flex-wrap items-start gap-5">
            <div class="bg-primary/10 flex size-20 shrink-0 items-center justify-center rounded-2xl">
              <GoupixDexCatalogSetLogo
                :logo="setDetail.logo"
                :symbol="setDetail.symbol"
                :cover="setDetail.cover"
                :set-id="setDetail.id"
                :name="setDisplayName"
                large
              />
            </div>
            <div class="min-w-0 flex-1 space-y-1">
              <p class="text-muted text-xs tracking-wide uppercase">Extension</p>
              <h1 class="text-highlighted text-2xl font-semibold tracking-tight">{{ setDisplayName }}</h1>
              <p class="text-muted flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                <span class="bg-muted/30 rounded px-1.5 py-0.5 font-mono text-xs uppercase">{{ setDetail.id }}</span>
                <span v-if="setDetail.serie?.name">{{ setDetail.serie.name }}</span>
                <span v-if="cardTotal">{{ cardTotal }} cartes</span>
                <span v-if="releaseLabel">{{ releaseLabel }}</span>
              </p>
            </div>
            <UBadge color="neutral" variant="subtle" class="shrink-0">
              Langue · {{ languageLabel(catalogLanguage) }}
            </UBadge>
          </div>

          <GoupixDexCatalogSetCards
            :cards="cardRows"
            :owned-by-card-id="ownedCards"
            :pending-card-id="pendingCardId"
            :scans-missing="scansMissing"
            @preview="onPreviewCard"
            @add="onAddCard"
          />
        </template>

        <UAlert
          v-else
          color="error"
          title="Extension introuvable"
          description="Cette extension n'existe pas dans TCGdex pour cette langue."
        />
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { CatalogLocale, TcgdexSetDetail } from '~/composables/useCardCatalog'
import type { CatalogSetCardRow } from '~/components/collection/GoupixDexCatalogSetCards.vue'
import { cardThumbFromImage } from '~/utils/catalogAssets'

definePageMeta({ middleware: 'auth' })

const route = useRoute()
const toast = useToast()
const { getSet } = useCardCatalog()
const { addToCollection, listCollection } = useCollection()
const { catalogLanguage } = useCatalogLanguage()
const drawerStack = useGoupixDrawerStack()

const setId = computed(() => String(route.params.setId ?? ''))

const catalogLocale = computed<CatalogLocale>(() => {
  const q = route.query.locale
  if (q === 'ja' || q === 'en' || q === 'fr') {
    return q
  }
  return catalogLanguage.value
})

const backToCatalogLink = computed(() => {
  const loc = catalogLocale.value
  return loc === 'fr' ? '/collection/add' : `/collection/add?locale=${encodeURIComponent(loc)}`
})

function languageLabel(code: CatalogLocale): string {
  switch (code) {
    case 'fr':
      return 'Français'
    case 'en':
      return 'English'
    case 'ja':
      return 'Japonais'
    default:
      return code
  }
}

const setDetail = ref<TcgdexSetDetail | null>(null)
const setLoading = ref(true)
const pendingCardId = ref<string | null>(null)
const ownedCards = ref<Map<string, number>>(new Map())

const setDisplayName = computed(() => {
  if (!setDetail.value) {
    return ''
  }
  return setDetail.value.display_name?.trim() || setDetail.value.name?.trim() || setDetail.value.id
})

const cardTotal = computed(() => {
  const n = setDetail.value?.cardCount?.total ?? setDetail.value?.cards?.length
  return n ? `${n}` : null
})

const releaseLabel = computed(() => {
  const raw = setDetail.value?.releaseDate
  if (!raw) {
    return null
  }
  try {
    return new Date(raw).toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' })
  } catch {
    return raw
  }
})

const scansMissing = computed(() => {
  const cards = setDetail.value?.cards ?? []
  return cards.length > 0 && cards.every((c) => !c.image && !c.image_low)
})

const cardRows = computed<CatalogSetCardRow[]>(() => {
  const raw = setDetail.value?.cards ?? []
  return [...raw]
    .sort((a, b) => a.localId.localeCompare(b.localId, 'en', { numeric: true }))
    .map((c) => ({
      id: c.id,
      localId: c.localId,
      displayName: c.display_name?.trim() || c.name,
      thumbUrl: cardThumbFromImage(c.image, c.image_low),
    }))
})

watch([setId, catalogLocale], () => {
  void loadSet()
})

watch(catalogLanguage, () => {
  void refreshOwnedIndex()
})

watch(
  () => drawerStack.cardMutationCounter.value,
  () => {
    void refreshOwnedIndex()
  },
)

async function loadSet(): Promise<void> {
  setLoading.value = true
  setDetail.value = null
  try {
    const res = await getSet(catalogLocale.value, setId.value)
    setDetail.value = res.set
    useGoupixPageSeo(setDisplayName.value, `Cartes de l’extension ${setDisplayName.value} — catalogue TCGdex.`)
  } catch (e) {
    toast.add({ title: 'Extension', description: apiErrorMessage(e), color: 'error' })
    setDetail.value = null
  } finally {
    setLoading.value = false
  }
}

/**
 * Ouvre l'aperçu (drawer) d'une carte de l'extension : image, prix, ajout.
 * @param c - Ligne de carte du set.
 * @returns {void}
 */
function onPreviewCard(c: CatalogSetCardRow): void {
  drawerStack.pushCatalogCard({
    id: c.id,
    name: c.displayName,
    setName: setDisplayName.value,
    localId: c.localId,
    image: c.thumbUrl ?? null,
    locale: catalogLocale.value,
  })
}

async function onAddCard(c: CatalogSetCardRow): Promise<void> {
  if (pendingCardId.value) {
    return
  }
  pendingCardId.value = c.id
  try {
    const res = await addToCollection({
      tcgdex_card_id: c.id,
      language: catalogLocale.value,
      quantity: 1,
    })
    ownedCards.value.set(c.id, res.card.quantity)
    toast.add({
      title: res.created ? 'Ajoutée à la collection' : `Quantité ×${res.card.quantity}`,
      description: c.displayName,
      color: 'success',
    })
  } catch (e) {
    toast.add({ title: 'Ajout impossible', description: apiErrorMessage(e), color: 'error' })
  } finally {
    pendingCardId.value = null
  }
}

async function refreshOwnedIndex(): Promise<void> {
  try {
    const res = await listCollection({ language: catalogLanguage.value })
    const map = new Map<string, number>()
    res.items.forEach((row) => map.set(row.tcgdex_card_id, row.quantity))
    ownedCards.value = map
  } catch {
    /* best-effort */
  }
}

onMounted(() => {
  const qLoc = route.query.locale
  if (qLoc === 'ja' || qLoc === 'en' || qLoc === 'fr') {
    catalogLanguage.value = qLoc
  }
  void loadSet()
  void refreshOwnedIndex()
})
</script>
