<template>
  <div class="space-y-4">
    <UAlert
      v-if="!isDesktopApp"
      color="info"
      variant="subtle"
      icon="i-lucide-sparkles"
      title="Mise en ligne Vinted disponible uniquement dans l'app desktop"
    >
      <template #description>
        <p class="text-sm leading-relaxed">
          Installez GoupixDex sur Windows ou macOS pour publier depuis votre connexion, comme sur la page
          <NuxtLink
            to="/downloads"
            class="text-primary decoration-primary/40 hover:decoration-primary font-medium underline underline-offset-2"
          >
            Télécharger l'app
          </NuxtLink>
          (installateurs et conseils pour choisir le bon fichier).
        </p>
      </template>
    </UAlert>

    <div v-if="loading && !filtered.length" class="app-card flex justify-center py-16">
      <UIcon name="i-lucide-loader-circle" class="h-8 w-8 animate-spin text-[var(--app-accent)]" />
    </div>

    <div v-else-if="!loading && !filtered.length" class="app-card px-6 py-12 text-center">
      <p class="text-sm text-[var(--app-ink-soft)]">
        {{ searchQuery.trim() ? 'Aucun résultat pour cette recherche.' : 'Aucun article.' }}
      </p>
    </div>

    <div v-else class="app-card overflow-hidden">
      <div class="border-b border-[var(--app-line)] p-4">
        <div class="relative w-full md:max-w-md">
          <UIcon
            name="i-lucide-search"
            class="pointer-events-none absolute top-1/2 left-3 h-3.5 w-3.5 -translate-y-1/2 text-[var(--app-faint)]"
          />
          <input
            v-model="searchQuery"
            type="search"
            placeholder="Rechercher : nom, set, série, n°…"
            aria-label="Rechercher un article"
            class="app-input pl-9"
          />
        </div>
      </div>

      <div
        v-if="selectedCount > 0"
        class="flex flex-col gap-2 border-b border-[var(--app-line)] bg-[var(--app-surface-2)]/60 px-4 py-2.5 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between"
      >
        <p class="text-sm text-[var(--app-ink)]">
          {{ selectedCount }} article{{ selectedCount > 1 ? 's' : '' }} sélectionné{{ selectedCount > 1 ? 's' : '' }}
        </p>
        <div class="flex flex-wrap gap-2">
          <UButton size="sm" color="neutral" variant="outline" @click="clearSelection"> Tout désélectionner </UButton>
          <UButton
            v-if="showBulkBoth"
            size="sm"
            color="primary"
            icon="i-lucide-upload-cloud"
            class="shadow-sm"
            :disabled="!!bulkBothDisabledReason || bulkPublishing"
            :title="bulkBothDisabledReason || undefined"
            :loading="bulkPublishing"
            @click="emit('bulk-publish-both', [...selectedIds])"
          >
            Mettre en ligne
          </UButton>
          <UButton
            v-if="showBulkVinted"
            size="sm"
            color="neutral"
            variant="solid"
            icon="i-lucide-store"
            class="border-0 !bg-[rgb(0,131,143)] !text-white hover:!bg-[rgb(0,118,129)] disabled:opacity-50"
            :disabled="!!bulkVintedDisabledReason || bulkPublishing"
            :title="bulkVintedDisabledReason || undefined"
            :loading="bulkPublishing"
            @click="emit('bulk-publish-vinted', [...selectedIds])"
          >
            Mettre en ligne sur Vinted
          </UButton>
          <UButton
            v-if="showBulkEbay"
            size="sm"
            color="neutral"
            variant="solid"
            icon="i-lucide-shopping-bag"
            class="border-0 !bg-[rgb(134,184,23)] !text-neutral-950 hover:!bg-[rgb(124,174,20)] disabled:opacity-50"
            :disabled="!!bulkEbayDisabledReason || bulkPublishing"
            :title="bulkEbayDisabledReason || undefined"
            :loading="bulkPublishing"
            @click="emit('bulk-publish-ebay', [...selectedIds])"
          >
            Mettre en ligne sur eBay
          </UButton>
          <UButton
            size="sm"
            color="success"
            variant="subtle"
            icon="i-lucide-circle-check"
            :disabled="!!bulkSoldDisabledReason || bulkPublishing"
            :title="bulkSoldDisabledReason || undefined"
            @click="emitBulkSold"
          >
            Marquer comme vendu
          </UButton>
          <UButton
            size="sm"
            color="error"
            icon="i-lucide-trash-2"
            :disabled="bulkPublishing"
            @click="emit('bulk-delete', [...selectedIds])"
          >
            Supprimer la sélection
          </UButton>
        </div>
      </div>

      <GoupixDexBaseTable :min-width="tableMinWidth">
        <template #head>
          <GoupixDexBaseTableTh class="w-12">
            <input
              type="checkbox"
              class="h-4 w-4 cursor-pointer accent-(--app-accent)"
              :checked="allFilteredSelected"
              :indeterminate.prop="someFilteredSelected && !allFilteredSelected"
              aria-label="Tout sélectionner sur cette page"
              @change="onToggleSelectAllNative"
            />
          </GoupixDexBaseTableTh>
          <GoupixDexBaseTableTh class="w-14" sr-only>Visuel</GoupixDexBaseTableTh>
          <GoupixDexBaseTableSortTh
            label="Nom"
            title="Nom de l'article"
            :active="sortColumn === 'name'"
            :direction="sortDirection"
            @sort="toggleSort('name')"
          />
          <GoupixDexBaseTableSortTh
            v-if="showSaleOutcomeColumns"
            label="Statut"
            title="Article vendu ou en stock"
            :active="sortColumn === 'sold'"
            :direction="sortDirection"
            @sort="toggleSort('sold')"
          />
          <GoupixDexBaseTableSortTh
            label="Set"
            title="Série / set"
            :active="sortColumn === 'set'"
            :direction="sortDirection"
            @sort="toggleSort('set')"
          />
          <GoupixDexBaseTableSortTh
            label="N°"
            title="Numéro de carte"
            :active="sortColumn === 'number'"
            :direction="sortDirection"
            @sort="toggleSort('number')"
          />
          <GoupixDexBaseTableSortTh
            label="Achat"
            title="Prix d'achat"
            align="right"
            :active="sortColumn === 'purchase'"
            :direction="sortDirection"
            @sort="toggleSort('purchase')"
          />
          <GoupixDexBaseTableSortTh
            label="Vente"
            title="Prix de vente affiché"
            align="right"
            :active="sortColumn === 'sell'"
            :direction="sortDirection"
            @sort="toggleSort('sell')"
          />
          <GoupixDexBaseTableSortTh
            v-if="showSaleOutcomeColumns"
            label="Réalisé"
            title="Prix réalisé"
            align="right"
            :active="sortColumn === 'realized'"
            :direction="sortDirection"
            @sort="toggleSort('realized')"
          />
          <GoupixDexBaseTableTh align="center">Vinted</GoupixDexBaseTableTh>
          <GoupixDexBaseTableTh v-if="showEbayColumn" align="center">eBay</GoupixDexBaseTableTh>
          <GoupixDexBaseTableSortTh
            label="Créé"
            title="Date de création"
            :active="sortColumn === 'created'"
            :direction="sortDirection"
            @sort="toggleSort('created')"
          />
          <GoupixDexBaseTableSortTh
            v-if="showSaleOutcomeColumns"
            label="Vendu le"
            title="Date de vente"
            :active="sortColumn === 'sold_at'"
            :direction="sortDirection"
            @sort="toggleSort('sold_at')"
          />
          <GoupixDexBaseTableTh align="center" sr-only>Actions</GoupixDexBaseTableTh>
        </template>

        <GoupixDexBaseTableTr
          v-for="row in cachedRows"
          v-show="idToPage.get(row.id) === page"
          :key="row.id"
          :class="isSelected(row.id) ? 'bg-[var(--app-accent-soft)] hover:bg-[var(--app-accent-soft)]' : ''"
        >
          <GoupixDexBaseTableTd class="w-12 align-middle">
            <input
              type="checkbox"
              class="h-4 w-4 cursor-pointer accent-(--app-accent)"
              :checked="isSelected(row.id)"
              :aria-label="`Sélectionner ${row.pokemon_name || row.title}`"
              @change="onToggleRowNative(row.id, $event)"
            />
          </GoupixDexBaseTableTd>

          <GoupixDexBaseTableTd class="goupix-card-table__lead w-14 align-middle">
            <a
              :href="articleDetailHref(row.id)"
              class="relative block size-10 shrink-0 overflow-hidden rounded-lg ring-1 ring-[var(--app-line)] md:size-11"
              :aria-label="row.pokemon_name || row.title"
              @click="onOpenArticle(row.id, $event)"
            >
              <img
                v-if="row.images?.length"
                :src="imageSrc(row.images[0]?.image_url)"
                :alt="row.title"
                loading="lazy"
                decoding="async"
                class="absolute inset-0 h-full w-full object-cover"
              />
              <span
                v-else
                class="absolute inset-0 flex items-center justify-center bg-[var(--app-surface-2)] text-xs font-semibold text-[var(--app-ink-soft)]"
              >
                {{ (row.pokemon_name || row.title || '?').slice(0, 2).toUpperCase() }}
              </span>
            </a>
            <div class="min-w-0 flex-1 md:hidden">
              <a
                :href="articleDetailHref(row.id)"
                class="block truncate text-sm font-semibold text-[var(--app-ink)] underline decoration-transparent underline-offset-4 transition-colors hover:decoration-[var(--app-accent)]"
                @click="onOpenArticle(row.id, $event)"
              >
                {{ row.pokemon_name || row.title || '—' }}
              </a>
              <p class="truncate text-xs text-[var(--app-ink-soft)]">{{ row.title }}</p>
            </div>
          </GoupixDexBaseTableTd>

          <GoupixDexBaseTableTd class="hidden min-w-[12rem] align-middle md:table-cell">
            <div class="flex flex-col gap-0.5">
              <a
                :href="articleDetailHref(row.id)"
                class="truncate text-sm font-semibold text-[var(--app-ink)] underline decoration-transparent underline-offset-4 transition-colors hover:decoration-[var(--app-accent)]"
                @click="onOpenArticle(row.id, $event)"
              >
                {{ row.pokemon_name || row.title || '—' }}
              </a>
              <span class="truncate text-xs text-[var(--app-ink-soft)]">{{ row.title }}</span>
            </div>
          </GoupixDexBaseTableTd>

          <GoupixDexBaseTableTd v-if="showSaleOutcomeColumns" label="Statut">
            <span v-if="!row.is_sold" class="app-badge app-badge--danger">
              {{ soldStatusLabel(row) }}
            </span>
            <span
              v-else-if="soldStatusBrandStyle(row)"
              class="inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-black/10"
              :style="soldStatusBrandStyle(row)!"
            >
              {{ soldStatusLabel(row) }}
            </span>
            <span v-else class="app-badge app-badge--success">
              <UIcon name="i-lucide-circle-check" class="h-3 w-3" />
              {{ soldStatusLabel(row) }}
            </span>
          </GoupixDexBaseTableTd>

          <GoupixDexBaseTableTd label="Set" class="text-[var(--app-ink-soft)]">
            {{ row.set_code || '—' }}
          </GoupixDexBaseTableTd>

          <GoupixDexBaseTableTd label="N°" class="tabular-nums">
            {{ row.card_number || '—' }}
          </GoupixDexBaseTableTd>

          <GoupixDexBaseTableTd label="Achat" align="right" class="text-[var(--app-ink)] tabular-nums">
            {{ eur.format(row.purchase_price) }}
          </GoupixDexBaseTableTd>

          <GoupixDexBaseTableTd label="Vente" align="right" class="text-[var(--app-ink-soft)] tabular-nums">
            {{ row.sell_price != null ? eur.format(row.sell_price) : '—' }}
          </GoupixDexBaseTableTd>

          <GoupixDexBaseTableTd
            v-if="showSaleOutcomeColumns"
            label="Réalisé"
            align="right"
            class="font-medium text-[var(--app-ink)] tabular-nums"
          >
            <span v-if="realizedSalePrice(row) != null">{{ eur.format(realizedSalePrice(row)!) }}</span>
            <span v-else class="text-[var(--app-faint)]">—</span>
          </GoupixDexBaseTableTd>

          <GoupixDexBaseTableTd label="Vinted" align="center">
            <span v-if="row.published_on_vinted ?? false" class="app-badge app-badge--success">
              <UIcon name="i-lucide-circle-check" class="h-3 w-3" />
              Oui
            </span>
            <span v-else class="text-[var(--app-faint)]">—</span>
          </GoupixDexBaseTableTd>

          <GoupixDexBaseTableTd v-if="showEbayColumn" label="eBay" align="center">
            <span v-if="row.published_on_ebay ?? false" class="app-badge app-badge--success">
              <UIcon name="i-lucide-circle-check" class="h-3 w-3" />
              Oui
            </span>
            <span v-else class="app-badge">Non</span>
          </GoupixDexBaseTableTd>

          <GoupixDexBaseTableTd label="Créé" class="text-xs whitespace-nowrap text-[var(--app-ink-soft)]">
            {{ new Date(row.created_at).toLocaleDateString('fr-FR') }}
          </GoupixDexBaseTableTd>

          <GoupixDexBaseTableTd
            v-if="showSaleOutcomeColumns"
            label="Vendu le"
            class="text-xs whitespace-nowrap text-[var(--app-ink-soft)]"
          >
            <span v-if="row.sold_at">{{ new Date(row.sold_at).toLocaleDateString('fr-FR') }}</span>
            <span v-else class="text-[var(--app-faint)]">—</span>
          </GoupixDexBaseTableTd>

          <GoupixDexBaseTableTd class="goupix-card-table__actions align-middle" label="Actions" align="center">
            <UDropdownMenu :items="buildRowMenu(row)">
              <UButton color="neutral" variant="ghost" icon="i-lucide-more-horizontal" square />
            </UDropdownMenu>
          </GoupixDexBaseTableTd>
        </GoupixDexBaseTableTr>
      </GoupixDexBaseTable>

      <div
        class="flex flex-col gap-3 border-t border-[var(--app-line)] bg-[var(--app-surface-2)]/50 px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between sm:px-6"
      >
        <div class="flex flex-wrap items-center gap-3">
          <p class="text-xs text-[var(--app-ink-soft)] tabular-nums">
            {{ paginationFrom }}–{{ paginationTo }} sur {{ filtered.length }} article{{
              filtered.length > 1 ? 's' : ''
            }}
          </p>
          <div class="flex items-center gap-2">
            <span class="text-xs text-[var(--app-ink-soft)]">Par page</span>
            <USelect
              v-model="pageSize"
              :items="PAGE_SIZE_ITEMS"
              value-key="value"
              label-key="label"
              size="sm"
              class="w-28"
            />
          </div>
        </div>
        <div class="flex items-center gap-2">
          <UButton
            color="neutral"
            variant="subtle"
            size="sm"
            icon="i-lucide-arrow-left"
            :disabled="page <= 1"
            @click="page = Math.max(1, page - 1)"
          >
            Précédent
          </UButton>
          <span class="px-1 text-xs text-[var(--app-ink-soft)] tabular-nums">Page {{ page }} / {{ totalPages }}</span>
          <UButton
            color="neutral"
            variant="subtle"
            size="sm"
            icon="i-lucide-arrow-right"
            :disabled="page >= totalPages"
            @click="page = Math.min(totalPages, page + 1)"
          >
            Suivant
          </UButton>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import type { ComputedRef, Ref } from 'vue'
import type { Article } from '~/composables/useArticles'
import type { ArticleListSortColumn, ArticleListSortDirection } from '~/composables/useUiPrefsLocalStorage'
import { loadArticleListPrefs, saveArticleListPrefs } from '~/composables/useUiPrefsLocalStorage'

export type GoupixDexArticleListVariant = 'listed' | 'full'

const props = withDefaults(
  defineProps<{
    articles: Article[]
    /** `listed` = onglet En vente (sans colonnes liées à une vente déjà conclue). */
    variant?: GoupixDexArticleListVariant
    loading?: boolean
    /** Incrémenté par la page parent après une vente pour vider la sélection. */
    selectionResetKey?: number
    /** Show the “listed on eBay” column (same gate as eBay publish actions). */
    showEbayColumn?: boolean
    /** eBay enabled + account connected + listing wizard complete (settings); hides eBay actions otherwise. */
    ebayPublishAvailable?: boolean
    /** Vinted enabled in Settings → marketplaces (otherwise the API rejects publish). */
    vintedChannelEnabled?: boolean
    /** Disable bulk publish buttons while an API call is in flight. */
    bulkPublishing?: boolean
  }>(),
  {
    variant: 'listed',
  },
)

const showSaleOutcomeColumns = computed(() => props.variant === 'full')

const tableMinWidth = computed(() => (showSaleOutcomeColumns.value ? '1120px' : '920px'))

const emit = defineEmits<{
  edit: [id: number]
  delete: [id: number]
  sold: [article: Article]
  'publish-vinted': [article: Article]
  'publish-ebay': [article: Article]
  'bulk-delete': [ids: number[]]
  'bulk-publish-vinted': [ids: number[]]
  'bulk-publish-ebay': [ids: number[]]
  'bulk-publish-both': [ids: number[]]
  'bulk-sold': [articles: Article[]]
  'retry-cross-ebay': [id: number]
  'retry-cross-vinted': [id: number]
}>()

const { isDesktopApp } = useDesktopRuntime()
const { openArticle, openArticleFromClick } = useOpenArticleDrawer()

/**
 * Whether the "publish on eBay" row action should be disabled.
 * @param row - Article row
 * @returns {boolean} True when the action is unavailable
 */
function ebayRowDisabled(row: Article): boolean {
  return row.is_sold || (row.published_on_ebay ?? false) || !row.images?.length
}

/**
 * Actions du menu « … » pour une ligne (inclut réessais suppression croisée).
 */
function buildRowMenu(row: Article) {
  const cross: {
    label: string
    icon: string
    disabled?: boolean
    onSelect: () => void
  }[] = []
  if (row.is_sold && row.sale_source === 'vinted' && row.cross_ebay_removal_failed) {
    cross.push({
      label: 'Réessayer suppression eBay',
      icon: 'i-lucide-refresh-ccw',
      onSelect: () => emit('retry-cross-ebay', row.id),
    })
  }
  if (row.pending_vinted_unlist && (row.cross_vinted_removal_failed || isDesktopApp.value)) {
    cross.push({
      label: 'Réessayer suppression Vinted',
      icon: 'i-lucide-refresh-ccw',
      disabled: !isDesktopApp.value,
      onSelect: () => emit('retry-cross-vinted', row.id),
    })
  }
  return [
    [
      { label: 'Voir la fiche', icon: 'i-lucide-panel-right', onSelect: () => openArticle(row.id, articleBrowseIds()) },
      { label: 'Modifier', icon: 'i-lucide-pencil', onSelect: () => emit('edit', row.id) },
      ...cross,
      {
        label: 'Mettre en ligne sur Vinted',
        icon: 'i-lucide-store',
        disabled: !isDesktopApp.value || row.is_sold || !row.images?.length,
        onSelect: () => emit('publish-vinted', row),
      },
      ...(props.ebayPublishAvailable
        ? [
            {
              label: 'Mettre en ligne sur eBay',
              icon: 'i-lucide-shopping-bag',
              disabled: ebayRowDisabled(row),
              onSelect: () => emit('publish-ebay', row),
            },
          ]
        : []),
      {
        label: 'Marquer vendu',
        icon: 'i-lucide-circle-check',
        disabled: row.is_sold,
        onSelect: () => emit('sold', row),
      },
      {
        label: 'Supprimer',
        icon: 'i-lucide-trash-2',
        color: 'error',
        onSelect: () => emit('delete', row.id),
      },
    ],
  ]
}

/**
 * Whether at least one attached image uses HTTPS (required for eBay bulk publish).
 * @param row - Article row
 * @returns {boolean} True when an HTTPS image exists
 */
function hasHttpsImage(row: Article): boolean {
  return row.images?.some((img) => (img.image_url || '').startsWith('https://')) ?? false
}

/**
 * Whether bulk Vinted publish applies to this row.
 * @param row - Article row
 * @returns {boolean} True when eligible
 */
function canBulkVinted(row: Article): boolean {
  return !row.is_sold && (row.images?.length ?? 0) > 0
}

/**
 * Whether bulk eBay publish applies to this row.
 * @param row - Article row
 * @returns {boolean} True when eligible
 */
function canBulkEbay(row: Article): boolean {
  return !row.is_sold && !(row.published_on_ebay ?? false) && hasHttpsImage(row)
}

/**
 * Short sold-status label for the badge column.
 * @param row - Article row
 * @returns {string} Display label
 */
function soldStatusLabel(row: Article): string {
  if (!row.is_sold) {
    return 'Non'
  }
  if (row.sale_source === 'ebay') {
    return 'eBay'
  }
  if (row.sale_source === 'vinted') {
    return 'Vinted'
  }
  return 'Oui'
}

/**
 * Best-effort realized sale amount from tracking fields.
 * @param row - Article row
 * @returns {number | null} Sold amount when known
 */
function realizedSalePrice(row: Article): number | null {
  if (!row.is_sold) {
    return null
  }
  if (row.sold_price != null) {
    return row.sold_price
  }
  return row.sell_price
}

/** Vinted / eBay brand colors for the sold-status badge when source is known */
const SOLD_BADGE_VINTED = '#00838f'
const SOLD_BADGE_EBAY = '#86b817'

/**
 * Badge colors when we know the marketplace source of the sale.
 * @param row - Article row
 * @returns {{ backgroundColor: string; color: string } | null} Inline styles or null
 */
function soldStatusBrandStyle(row: Article): { backgroundColor: string; color: string } | null {
  if (!row.is_sold) {
    return null
  }
  if (row.sale_source === 'vinted') {
    return { backgroundColor: SOLD_BADGE_VINTED, color: '#ffffff' }
  }
  if (row.sale_source === 'ebay') {
    return { backgroundColor: SOLD_BADGE_EBAY, color: '#ffffff' }
  }
  return null
}

const sortColumn: Ref<ArticleListSortColumn> = ref('created')
const sortDirection: Ref<ArticleListSortDirection> = ref('desc')

const SALE_OUTCOME_SORT_COLUMNS: ArticleListSortColumn[] = ['sold', 'realized', 'sold_at']

watch(
  showSaleOutcomeColumns,
  (show) => {
    if (!show && SALE_OUTCOME_SORT_COLUMNS.includes(sortColumn.value)) {
      sortColumn.value = 'created'
      sortDirection.value = 'desc'
    }
  },
  { immediate: true },
)

/** Text filter: name, set code, set name, card #, title. */
const searchQuery: Ref<string> = ref('')

const PAGE_SIZE_ITEMS = [
  { label: '5', value: 5 },
  { label: '10', value: 10 },
  { label: '15', value: 15 },
  { label: '30', value: 30 },
  { label: '50', value: 50 },
  { label: '100', value: 100 },
]

const page: Ref<number> = ref(1)
const pageSize: Ref<number> = ref(10)

onMounted(() => {
  const s = loadArticleListPrefs()
  if (s?.sortColumn) {
    sortColumn.value = s.sortColumn
  }
  if (s?.sortDirection) {
    sortDirection.value = s.sortDirection
  }
  if (s?.searchQuery != null) {
    searchQuery.value = s.searchQuery
  }
  if (typeof s?.pageSize === 'number') {
    pageSize.value = s.pageSize
  }
})

watch([sortColumn, sortDirection, searchQuery, pageSize], () => {
  saveArticleListPrefs({
    sortColumn: sortColumn.value,
    sortDirection: sortDirection.value,
    searchQuery: searchQuery.value,
    pageSize: pageSize.value,
  })
})

/**
 * Normalize user search input for accent-insensitive matching.
 * @param s - Raw query fragment
 * @returns {string} Lowercase ASCII-ish form
 */
function normalizeSearch(s: string): string {
  return s.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase()
}

/**
 * Concatenate searchable fields for one article row.
 * @param row - Article row
 * @returns {string} Haystack text for filtering
 */
function articleSearchText(row: Article): string {
  return [row.pokemon_name, row.set_code, row.card_number, row.title]
    .filter((x): x is string => Boolean(x && String(x).trim()))
    .join(' ')
}

const eur = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 2,
})

const filtered: ComputedRef<Article[]> = computed(() => {
  let rows = [...props.articles]

  const rawQ = searchQuery.value.trim()
  if (rawQ) {
    const tokens = normalizeSearch(rawQ).split(/\s+/).filter(Boolean)
    rows = rows.filter((row) => {
      const hay = normalizeSearch(articleSearchText(row))
      return tokens.every((t) => hay.includes(t))
    })
  }

  rows.sort((a, b) => compareArticlesForSort(a, b, sortColumn.value, sortDirection.value))
  return rows
})

const paginationFrom = computed(() => {
  if (!filtered.value.length) {
    return 0
  }
  return (page.value - 1) * pageSize.value + 1
})

const paginationTo = computed(() => Math.min(page.value * pageSize.value, filtered.value.length))

function articleBrowseIds(): number[] {
  return filtered.value.map((row) => row.id)
}

function articleDetailHref(rowId: number): string {
  return `/articles/${rowId}`
}

function onOpenArticle(rowId: number, event: MouseEvent): void {
  openArticleFromClick(rowId, event, articleBrowseIds())
}

/**
 * Default direction when the user activates a new sort column.
 */
function defaultSortDirection(column: ArticleListSortColumn): ArticleListSortDirection {
  if (column === 'name' || column === 'set' || column === 'number') {
    return 'asc'
  }
  return 'desc'
}

function toggleSort(column: ArticleListSortColumn): void {
  if (sortColumn.value === column) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
    return
  }
  sortColumn.value = column
  sortDirection.value = defaultSortDirection(column)
}

/**
 * Sort key for display name (Pokémon name or listing title).
 */
function articleDisplayName(row: Article): string {
  return (row.pokemon_name || row.title || '').trim()
}

/**
 * Compare two ISO date strings; empty values sort last in ascending order.
 */
function compareOptionalDate(
  a: string | null | undefined,
  b: string | null | undefined,
  dir: ArticleListSortDirection,
): number {
  const ta = a ? new Date(a).getTime() : Number.NaN
  const tb = b ? new Date(b).getTime() : Number.NaN
  const aMissing = Number.isNaN(ta)
  const bMissing = Number.isNaN(tb)
  if (aMissing && bMissing) {
    return 0
  }
  if (aMissing) {
    return dir === 'asc' ? 1 : -1
  }
  if (bMissing) {
    return dir === 'asc' ? -1 : 1
  }
  const diff = ta - tb
  return dir === 'asc' ? diff : -diff
}

/**
 * Compare nullable numbers; nulls sort last in ascending order.
 */
function compareOptionalNumber(
  a: number | null | undefined,
  b: number | null | undefined,
  dir: ArticleListSortDirection,
): number {
  const aMissing = a == null
  const bMissing = b == null
  if (aMissing && bMissing) {
    return 0
  }
  if (aMissing) {
    return dir === 'asc' ? 1 : -1
  }
  if (bMissing) {
    return dir === 'asc' ? -1 : 1
  }
  const diff = a - b
  return dir === 'asc' ? diff : -diff
}

function compareArticlesForSort(
  a: Article,
  b: Article,
  column: ArticleListSortColumn,
  dir: ArticleListSortDirection,
): number {
  let cmp = 0
  switch (column) {
    case 'name':
      cmp = articleDisplayName(a).localeCompare(articleDisplayName(b), 'fr', { sensitivity: 'base' })
      break
    case 'sold': {
      const aSold = a.is_sold ? 1 : 0
      const bSold = b.is_sold ? 1 : 0
      cmp = aSold - bSold
      if (cmp === 0) {
        cmp = compareOptionalDate(a.sold_at, b.sold_at, 'desc')
        return dir === 'asc' ? cmp : -cmp
      }
      break
    }
    case 'set':
      cmp = (a.set_code || '').localeCompare(b.set_code || '', 'fr', { sensitivity: 'base' })
      break
    case 'number':
      cmp = (a.card_number || '').localeCompare(b.card_number || '', 'fr', { numeric: true, sensitivity: 'base' })
      break
    case 'purchase':
      cmp = a.purchase_price - b.purchase_price
      break
    case 'sell':
      cmp = compareOptionalNumber(a.sell_price, b.sell_price, 'asc')
      return dir === 'asc' ? cmp : -cmp
    case 'realized':
      cmp = compareOptionalNumber(realizedSalePrice(a), realizedSalePrice(b), 'asc')
      return dir === 'asc' ? cmp : -cmp
    case 'created':
      cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      break
    case 'sold_at':
      cmp = compareOptionalDate(a.sold_at, b.sold_at, 'asc')
      return dir === 'asc' ? cmp : -cmp
    default:
      return 0
  }
  return dir === 'asc' ? cmp : -cmp
}

watch([sortColumn, sortDirection, searchQuery, pageSize], () => {
  page.value = 1
})

const totalPages: ComputedRef<number> = computed(() => {
  const total = filtered.value.length
  const size = Math.max(1, pageSize.value)
  return Math.max(1, Math.ceil(total / size))
})

watch(
  [totalPages, page],
  ([tp, p]) => {
    if (p > tp) {
      page.value = tp
    } else if (p < 1) {
      page.value = 1
    }
  },
  { immediate: true },
)

const paged: ComputedRef<Article[]> = computed(() => {
  const p = Math.max(1, page.value)
  const size = Math.max(1, pageSize.value)
  const start = (p - 1) * size
  return filtered.value.slice(start, start + size)
})

/**
 * In-memory thumbnail cache (URL -> objectURL).
 * This avoids re-downloading small images when navigating back & forth,
 * even if the remote server sends no-cache / no-store headers.
 */
const IMAGE_CACHE_MAX = 250
const imageObjectUrlBySrc = reactive(new Map<string, string>())
const imageFetchInflight = reactive(new Set<string>())

function imageSrc(src?: string | null): string | undefined {
  if (!src) {
    return undefined
  }
  return imageObjectUrlBySrc.get(src) ?? src
}

/**
 * Keep a small LRU of rendered pages so <img> nodes don't get destroyed/recreated
 * when you navigate Next/Prev. This prevents refetch even when HTTP caching is disabled.
 */
const PAGE_DOM_CACHE_MAX = 3
const cachedPages: Ref<number[]> = ref([1])

const idToPage: ComputedRef<Map<number, number>> = computed(() => {
  const m = new Map<number, number>()
  const size = Math.max(1, pageSize.value)
  for (let i = 0; i < filtered.value.length; i += 1) {
    const row = filtered.value[i]
    if (!row) continue
    m.set(row.id, Math.floor(i / size) + 1)
  }
  return m
})

const cachedRows: ComputedRef<Article[]> = computed(() => {
  const wanted = new Set(cachedPages.value)
  return filtered.value.filter((row) => wanted.has(idToPage.value.get(row.id) ?? -1))
})

function touchCachedPage(p: number) {
  const next = cachedPages.value.filter((x) => x !== p)
  next.push(p)
  while (next.length > PAGE_DOM_CACHE_MAX) {
    next.shift()
  }
  cachedPages.value = next
}

watch(
  page,
  (p) => {
    touchCachedPage(p)
  },
  { immediate: true },
)

watch([sortColumn, sortDirection, searchQuery, pageSize], () => {
  cachedPages.value = [1]
})

function evictOldestImageCacheEntries() {
  while (imageObjectUrlBySrc.size > IMAGE_CACHE_MAX) {
    const oldestKey = imageObjectUrlBySrc.keys().next().value as string | undefined
    if (!oldestKey) {
      return
    }
    const objUrl = imageObjectUrlBySrc.get(oldestKey)
    imageObjectUrlBySrc.delete(oldestKey)
    if (objUrl) {
      URL.revokeObjectURL(objUrl)
    }
  }
}

async function cacheImageAsObjectUrl(src: string) {
  if (!src || imageObjectUrlBySrc.has(src) || imageFetchInflight.has(src)) {
    return
  }
  imageFetchInflight.add(src)
  try {
    const res = await fetch(src, { cache: 'force-cache' })
    if (!res.ok) {
      return
    }
    const blob = await res.blob()
    // Skip huge blobs just in case the URL points to a full-size image.
    if (blob.size > 2_500_000) {
      return
    }
    const objUrl = URL.createObjectURL(blob)
    imageObjectUrlBySrc.set(src, objUrl)
    evictOldestImageCacheEntries()
  } catch {
    // If CORS blocks fetch, the <img> / UAvatar can still load via direct URL.
  } finally {
    imageFetchInflight.delete(src)
  }
}

function prefetchPageImages(targetPage: number) {
  const size = Math.max(1, pageSize.value)
  const tp = totalPages.value
  if (targetPage < 1 || targetPage > tp) {
    return
  }
  const start = (targetPage - 1) * size
  const rows = filtered.value.slice(start, start + size)
  for (const row of rows) {
    const url = row.images?.[0]?.image_url
    if (typeof url === 'string' && url) {
      void cacheImageAsObjectUrl(url)
    }
  }
}

function schedulePrefetchAdjacentPages() {
  const next = page.value + 1
  const prev = page.value - 1
  const run = () => {
    prefetchPageImages(next)
    prefetchPageImages(prev)
  }
  if (import.meta.client && 'requestIdleCallback' in window) {
    ;(
      window as unknown as { requestIdleCallback: (cb: () => void, opts?: { timeout?: number }) => void }
    ).requestIdleCallback(run, { timeout: 1500 })
  } else {
    setTimeout(run, 50)
  }
}

watch(
  [page, pageSize, filtered],
  () => {
    if (!import.meta.client) {
      return
    }
    schedulePrefetchAdjacentPages()
    // Always cache the current page eagerly (prefetch does adjacent pages in idle time).
    prefetchPageImages(page.value)
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  for (const objUrl of imageObjectUrlBySrc.values()) {
    URL.revokeObjectURL(objUrl)
  }
  imageObjectUrlBySrc.clear()
  imageFetchInflight.clear()
})

/** Multi-row selection (ids visible in the current list) */
const selectedIds: Ref<number[]> = ref([])

watch(
  () =>
    props.articles
      .map((a) => a.id)
      .sort((a, b) => a - b)
      .join(','),
  () => {
    const valid = new Set(props.articles.map((a) => a.id))
    selectedIds.value = selectedIds.value.filter((id) => valid.has(id))
  },
)

const selectedRows: ComputedRef<Article[]> = computed(() =>
  props.articles.filter((a) => selectedIds.value.includes(a.id)),
)

const bulkVintedDisabledReason: ComputedRef<string> = computed(() => {
  if (!props.vintedChannelEnabled) {
    return 'Activez Vinted dans les paramètres marché.'
  }
  if (!isDesktopApp.value) {
    return 'La publication Vinted groupée nécessite l’application desktop.'
  }
  if (selectedRows.value.some((a) => !canBulkVinted(a))) {
    return 'Tous les articles sélectionnés doivent être non vendus et avoir au moins une photo.'
  }
  return ''
})

const bulkEbayDisabledReason: ComputedRef<string> = computed(() => {
  if (!props.ebayPublishAvailable) {
    return 'eBay n’est pas prêt (connexion OAuth et configuration des annonces).'
  }
  if (selectedRows.value.some((a) => !canBulkEbay(a))) {
    return 'Articles non vendus, pas déjà sur eBay, avec au moins une image en HTTPS.'
  }
  return ''
})

const bulkBothDisabledReason: ComputedRef<string> = computed(() => {
  if (!props.vintedChannelEnabled || !props.ebayPublishAvailable) {
    return 'Activez Vinted et eBay dans les paramètres, et terminez la configuration eBay.'
  }
  if (!isDesktopApp.value) {
    return 'Le duo eBay + Vinted nécessite l’application desktop pour Vinted.'
  }
  if (selectedRows.value.some((a) => !canBulkVinted(a) || !canBulkEbay(a))) {
    return 'Chaque article doit être éligible à la fois pour Vinted (photos) et pour eBay (HTTPS, pas déjà publié).'
  }
  return ''
})

const bulkSoldDisabledReason: ComputedRef<string> = computed(() => {
  if (!selectedRows.value.length) {
    return ''
  }
  if (selectedRows.value.some((a) => a.is_sold)) {
    return 'Ne sélectionnez que des articles non vendus.'
  }
  return ''
})

const showBulkVinted: ComputedRef<boolean> = computed(() => props.vintedChannelEnabled === true)
const showBulkEbay: ComputedRef<boolean> = computed(() => props.ebayPublishAvailable === true)
/** Shown when both channels are ready (disabled on web: see bulkBothDisabledReason). */
const showBulkBoth: ComputedRef<boolean> = computed(
  () => props.vintedChannelEnabled === true && props.ebayPublishAvailable === true,
)

const selectedCount: ComputedRef<number> = computed(() => selectedIds.value.length)

const allFilteredSelected: ComputedRef<boolean> = computed(
  () => paged.value.length > 0 && paged.value.every((r) => selectedIds.value.includes(r.id)),
)

const someFilteredSelected: ComputedRef<boolean> = computed(() =>
  paged.value.some((r) => selectedIds.value.includes(r.id)),
)

/**
 * Whether the article id is part of the current multi-selection.
 * @param id - Article id
 * @returns {boolean} Selection state
 */
function isSelected(id: number): boolean {
  return selectedIds.value.includes(id)
}

/**
 * Toggle one article id in the selection list.
 * @param id - Article id
 * @param checked - Checkbox tri-state from Nuxt UI table
 * @returns {void} Nothing
 */
function toggleId(id: number, checked: boolean | 'indeterminate'): void {
  if (checked === 'indeterminate') {
    return
  }
  if (checked) {
    if (!selectedIds.value.includes(id)) {
      selectedIds.value = [...selectedIds.value, id]
    }
  } else {
    selectedIds.value = selectedIds.value.filter((i) => i !== id)
  }
}

/**
 * Select or clear all rows currently visible after filters.
 * @param checked - Header checkbox tri-state
 * @returns {void} Nothing
 */
function toggleSelectAll(checked: boolean | 'indeterminate'): void {
  if (checked === 'indeterminate') {
    return
  }
  const fids = paged.value.map((r) => r.id)
  if (checked) {
    const s = new Set(selectedIds.value)
    fids.forEach((id) => s.add(id))
    selectedIds.value = [...s]
  } else {
    const rm = new Set(fids)
    selectedIds.value = selectedIds.value.filter((id) => !rm.has(id))
  }
}

function onToggleSelectAllNative(event: Event): void {
  toggleSelectAll((event.target as HTMLInputElement).checked)
}

function onToggleRowNative(id: number, event: Event): void {
  toggleId(id, (event.target as HTMLInputElement).checked)
}

function clearSelection() {
  selectedIds.value = []
}

watch(
  () => props.selectionResetKey,
  (_, prev) => {
    if (prev === undefined) {
      return
    }
    clearSelection()
  },
)

/**
 * Ouvre la vente groupée : uniquement les lignes non vendues, dans l’ordre de sélection.
 */
function emitBulkSold() {
  const rows: Article[] = []
  const seen = new Set<number>()
  for (const id of selectedIds.value) {
    if (seen.has(id)) {
      continue
    }
    seen.add(id)
    const a = props.articles.find((x) => x.id === id)
    if (a && !a.is_sold) {
      rows.push(a)
    }
  }
  if (!rows.length) {
    return
  }
  emit('bulk-sold', rows)
}
</script>
