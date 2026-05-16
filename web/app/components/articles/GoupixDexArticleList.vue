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

    <!-- Search left, filters right (md+); stacked on very small screens -->
    <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between md:gap-4">
      <UInput
        v-model="searchQuery"
        icon="i-lucide-search"
        placeholder="Rechercher : nom, set, série, n°…"
        class="w-full min-w-0 md:max-w-xl md:flex-1"
      />

      <div
        class="flex w-full flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center md:w-auto md:shrink-0 md:justify-end"
      >
        <div class="flex w-full flex-wrap gap-2 sm:w-auto sm:justify-end">
          <USelect
            v-model="filterSold"
            :items="[
              { label: 'Tous', value: 'all' },
              { label: 'En stock', value: 'unsold' },
              { label: 'Vendus', value: 'sold' },
            ]"
            value-key="value"
            label-key="label"
            class="min-w-0 flex-1 sm:w-44 sm:flex-none"
          />
          <USelect
            v-model="sortKey"
            :items="[
              { label: 'Date création ↓', value: 'created_desc' },
              { label: 'Date vente ↓', value: 'sold_desc' },
              { label: 'Prix achat ↑', value: 'purchase_asc' },
              { label: 'Prix achat ↓', value: 'purchase_desc' },
            ]"
            value-key="value"
            label-key="label"
            class="min-w-0 flex-1 sm:w-52 sm:flex-none"
          />
        </div>
      </div>
    </div>

    <div
      v-if="!loading && filtered.length > 0"
      class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"
    >
      <div class="flex items-center gap-2">
        <p class="text-muted text-xs">Par page</p>
        <USelect v-model="pageSize" :items="PAGE_SIZE_ITEMS" value-key="value" label-key="label" class="w-32" />
      </div>

      <div class="flex items-center justify-between gap-2 sm:justify-end">
        <p class="text-muted text-xs tabular-nums">Page {{ page }} / {{ totalPages }}</p>
        <div class="flex items-center gap-2">
          <UButton
            color="neutral"
            variant="subtle"
            icon="i-lucide-arrow-left"
            :disabled="page <= 1"
            @click="page = Math.max(1, page - 1)"
          >
            Précédent
          </UButton>
          <UButton
            color="neutral"
            variant="subtle"
            icon="i-lucide-arrow-right"
            :disabled="page >= totalPages"
            @click="page = Math.min(totalPages, page + 1)"
          >
            Suivant
          </UButton>
        </div>
      </div>
    </div>

    <div
      v-if="selectedCount > 0"
      class="border-default bg-elevated/95 supports-[backdrop-filter]:bg-elevated/85 sticky top-0 z-30 flex flex-col gap-2 rounded-lg border px-3 py-2.5 shadow-md shadow-black/5 backdrop-blur sm:flex-row sm:flex-wrap sm:items-center sm:justify-between"
    >
      <p class="text-highlighted text-sm">
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

    <div class="ring-default hidden overflow-x-auto rounded-lg ring lg:block">
      <table class="min-w-full border-separate border-spacing-0 text-sm">
        <thead class="bg-elevated/60 text-muted text-left text-xs uppercase">
          <tr>
            <th
              class="border-default bg-elevated sticky left-0 z-20 w-10 border-r border-b px-3 py-2 align-middle font-medium"
            >
              <UCheckbox
                :model-value="allFilteredSelected"
                :indeterminate="someFilteredSelected && !allFilteredSelected"
                aria-label="Tout sélectionner sur cette page"
                @update:model-value="toggleSelectAll"
              />
            </th>
            <th class="border-default w-12 border-b px-3 py-2 font-medium" />
            <th class="border-default border-b px-3 py-2 font-medium">Nom de l'article</th>
            <th class="border-default border-b px-3 py-2 font-medium">Vendu</th>
            <th class="border-default border-b px-3 py-2 font-medium">Série / set</th>
            <th class="border-default border-b px-3 py-2 font-medium">N°</th>
            <th class="border-default border-b px-3 py-2 font-medium">Prix d'achat</th>
            <th class="border-default border-b px-3 py-2 font-medium">Prix de vente</th>
            <th class="border-default border-b px-3 py-2 font-medium">Prix réalisé</th>
            <th class="border-default border-b px-3 py-2 font-medium">Vinted</th>
            <th v-if="showEbayColumn" class="border-default border-b px-3 py-2 font-medium">eBay</th>
            <th class="border-default border-b px-3 py-2 font-medium">Dates</th>
            <th class="border-default border-b px-3 py-2 text-end font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in cachedRows"
            v-show="idToPage.get(row.id) === page"
            :key="row.id"
            class="group border-default hover:bg-elevated/40 border-t"
          >
            <td
              class="border-default bg-default group-hover:bg-elevated/40 sticky left-0 z-10 border-r border-b px-3 py-3 align-middle transition-colors"
            >
              <UCheckbox
                :model-value="isSelected(row.id)"
                :aria-label="`Sélectionner ${row.pokemon_name || row.title}`"
                @update:model-value="(v) => toggleId(row.id, v)"
              />
            </td>
            <td class="border-default border-b px-3 py-3 align-middle">
              <UAvatar
                v-if="row.images?.length"
                size="lg"
                :src="imageSrc(row.images[0]?.image_url)"
                :alt="row.title"
                class="ring-default/80 ring-1"
              />
              <div v-else class="bg-elevated text-muted flex size-9 items-center justify-center rounded-full text-xs">
                {{ (row.pokemon_name || row.title || '?').slice(0, 2).toUpperCase() }}
              </div>
            </td>
            <td class="text-highlighted border-default border-b px-3 py-3 align-middle font-medium">
              <div class="flex flex-col gap-0.5">
                <NuxtLink
                  :to="`/articles/${row.id}`"
                  class="text-primary hover:text-primary/80 truncate font-medium underline-offset-2 hover:underline"
                >
                  {{ row.pokemon_name || row.title || '—' }}
                </NuxtLink>
                <span class="text-muted truncate text-xs">
                  {{ row.title }}
                </span>
              </div>
            </td>
            <td class="border-default border-b px-3 py-3 align-middle">
              <UBadge
                v-if="!row.is_sold"
                color="error"
                variant="subtle"
                class="max-w-[10rem] text-center leading-snug whitespace-normal"
              >
                {{ soldStatusLabel(row) }}
              </UBadge>
              <span
                v-else-if="soldStatusBrandStyle(row)"
                class="inline-flex max-w-[10rem] rounded-md px-2 py-0.5 text-center text-xs leading-snug font-semibold whitespace-normal ring-1 ring-black/10"
                :style="soldStatusBrandStyle(row)!"
              >
                {{ soldStatusLabel(row) }}
              </span>
              <UBadge
                v-else
                color="success"
                variant="subtle"
                class="max-w-[10rem] text-center leading-snug whitespace-normal"
              >
                {{ soldStatusLabel(row) }}
              </UBadge>
            </td>
            <td class="text-muted border-default border-b px-3 py-3 align-middle">
              {{ row.set_code || '—' }}
            </td>
            <td class="border-default border-b px-3 py-3 align-middle">
              {{ row.card_number || '—' }}
            </td>
            <td class="border-default border-b px-3 py-3 align-middle">
              {{ eur.format(row.purchase_price) }}
            </td>
            <td class="border-default border-b px-3 py-3 align-middle">
              {{ row.sell_price != null ? eur.format(row.sell_price) : '—' }}
            </td>
            <td class="border-default border-b px-3 py-3 align-middle">
              <span v-if="realizedSalePrice(row) != null">
                {{ eur.format(realizedSalePrice(row)!) }}
              </span>
              <span v-else class="text-muted">—</span>
            </td>
            <td class="border-default border-b px-3 py-3 align-middle">
              <UBadge v-if="row.published_on_vinted ?? false" color="success" variant="subtle">Oui</UBadge>
              <span v-else class="text-muted text-sm">—</span>
            </td>
            <td v-if="showEbayColumn" class="border-default border-b px-3 py-3 align-middle">
              <UBadge :color="(row.published_on_ebay ?? false) ? 'success' : 'neutral'" variant="subtle">
                {{ (row.published_on_ebay ?? false) ? 'Oui' : 'Non' }}
              </UBadge>
            </td>
            <td class="text-muted border-default border-b px-3 py-3 align-middle text-xs whitespace-nowrap">
              <div>Créé le {{ new Date(row.created_at).toLocaleDateString('fr-FR') }}</div>
              <div v-if="row.sold_at">Vendu le {{ new Date(row.sold_at).toLocaleDateString('fr-FR') }}</div>
            </td>
            <td class="border-default border-b px-3 py-3 text-end align-middle">
              <UDropdownMenu :items="buildRowMenu(row)">
                <UButton color="neutral" variant="ghost" icon="i-lucide-more-horizontal" square />
              </UDropdownMenu>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="space-y-3 lg:hidden">
      <div v-for="row in cachedRows" v-show="idToPage.get(row.id) === page" :key="row.id" class="w-full">
        <UCard class="border-default/80 bg-elevated/70 w-full border" :ui="{ body: 'p-3 space-y-3' }">
          <div class="flex items-start gap-3">
            <div class="shrink-0 pt-1">
              <UCheckbox
                :model-value="isSelected(row.id)"
                :aria-label="`Sélectionner ${row.pokemon_name || row.title}`"
                @update:model-value="(v) => toggleId(row.id, v)"
              />
            </div>
            <div class="min-w-0 flex-1 space-y-2">
              <div class="flex gap-3">
                <div
                  v-if="row.images?.length"
                  class="bg-elevated ring-default w-20 shrink-0 overflow-hidden rounded-lg ring"
                >
                  <img
                    :src="row.images[0]!.image_url"
                    :alt="row.title"
                    width="80"
                    height="80"
                    loading="lazy"
                    decoding="async"
                    fetchpriority="low"
                    class="h-20 w-full object-cover"
                  />
                </div>
                <div class="min-w-0 flex-1 space-y-1">
                  <NuxtLink
                    :to="`/articles/${row.id}`"
                    class="text-primary block truncate font-medium underline-offset-2 hover:underline"
                  >
                    {{ row.pokemon_name || row.title }}
                  </NuxtLink>
                  <p class="text-muted truncate text-xs">{{ row.set_code || '—' }} · {{ row.card_number || '—' }}</p>
                  <div class="flex flex-wrap gap-1.5 text-[11px]">
                    <UBadge v-if="!row.is_sold" color="error" variant="subtle">
                      {{ soldStatusLabel(row) }}
                    </UBadge>
                    <span
                      v-else-if="soldStatusBrandStyle(row)"
                      class="inline-flex rounded-md px-1.5 py-0.5 font-semibold ring-1 ring-black/10"
                      :style="soldStatusBrandStyle(row)!"
                    >
                      {{ soldStatusLabel(row) }}
                    </span>
                    <UBadge v-else color="success" variant="subtle">
                      {{ soldStatusLabel(row) }}
                    </UBadge>
                    <UBadge :color="(row.published_on_vinted ?? false) ? 'success' : 'neutral'" variant="subtle">
                      {{ (row.published_on_vinted ?? false) ? 'Vinted oui' : 'Vinted' }}
                    </UBadge>
                    <UBadge
                      v-if="showEbayColumn"
                      :color="(row.published_on_ebay ?? false) ? 'success' : 'neutral'"
                      variant="subtle"
                    >
                      eBay {{ (row.published_on_ebay ?? false) ? 'oui' : 'non' }}
                    </UBadge>
                    <span class="text-muted"> Achat {{ eur.format(row.purchase_price) }} </span>
                    <span class="text-muted">
                      Prix affiché {{ row.sell_price != null ? eur.format(row.sell_price) : '—' }}
                    </span>
                    <span v-if="row.is_sold" class="text-muted">
                      Réalisé {{ realizedSalePrice(row) != null ? eur.format(realizedSalePrice(row)!) : '—' }}
                    </span>
                  </div>
                </div>
              </div>
              <div class="flex flex-wrap justify-end gap-2">
                <UButton size="sm" variant="outline" @click="emit('edit', row.id)"> Modifier </UButton>
                <UButton
                  size="sm"
                  variant="outline"
                  icon="i-lucide-store"
                  :disabled="!isDesktopApp || row.is_sold || !row.images?.length"
                  @click="emit('publish-vinted', row)"
                >
                  Vinted
                </UButton>
                <UButton
                  v-if="ebayPublishAvailable"
                  size="sm"
                  variant="outline"
                  icon="i-lucide-shopping-bag"
                  :disabled="ebayRowDisabled(row)"
                  @click="emit('publish-ebay', row)"
                >
                  eBay
                </UButton>
                <UButton
                  v-if="row.is_sold && row.sale_source === 'vinted' && row.cross_ebay_removal_failed"
                  size="sm"
                  variant="outline"
                  icon="i-lucide-refresh-ccw"
                  @click="emit('retry-cross-ebay', row.id)"
                >
                  Réessayer eBay
                </UButton>
                <UButton
                  v-if="row.pending_vinted_unlist && (row.cross_vinted_removal_failed || isDesktopApp)"
                  size="sm"
                  variant="outline"
                  icon="i-lucide-refresh-ccw"
                  :disabled="!isDesktopApp"
                  @click="emit('retry-cross-vinted', row.id)"
                >
                  Réessayer Vinted
                </UButton>
                <UButton size="sm" :disabled="row.is_sold" @click="emit('sold', row)"> Vendu </UButton>
                <UButton size="sm" color="error" variant="soft" @click="emit('delete', row.id)"> Supprimer </UButton>
              </div>
            </div>
          </div>
        </UCard>
      </div>
    </div>

    <div v-if="!loading && !filtered.length" class="text-muted py-12 text-center">
      {{ searchQuery.trim() ? 'Aucun résultat pour cette recherche.' : 'Aucun article.' }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import type { ComputedRef, Ref } from 'vue'
import type { Article } from '~/composables/useArticles'
import type { ArticleListFilterSold, ArticleListSortKey } from '~/composables/useUiPrefsLocalStorage'
import { loadArticleListPrefs, saveArticleListPrefs } from '~/composables/useUiPrefsLocalStorage'

const props = defineProps<{
  articles: Article[]
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
}>()

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

const filterSold: Ref<ArticleListFilterSold> = ref('unsold')
const sortKey: Ref<ArticleListSortKey> = ref('created_desc')
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
  if (s?.filterSold) {
    filterSold.value = s.filterSold
  }
  if (s?.sortKey) {
    sortKey.value = s.sortKey
  }
  if (s?.searchQuery != null) {
    searchQuery.value = s.searchQuery
  }
  if (typeof s?.pageSize === 'number') {
    pageSize.value = s.pageSize
  }
})

watch([filterSold, sortKey, searchQuery, pageSize], () => {
  saveArticleListPrefs({
    filterSold: filterSold.value,
    sortKey: sortKey.value,
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
  if (filterSold.value === 'sold') {
    rows = rows.filter((r) => r.is_sold)
  } else if (filterSold.value === 'unsold') {
    rows = rows.filter((r) => !r.is_sold)
  }

  const rawQ = searchQuery.value.trim()
  if (rawQ) {
    const tokens = normalizeSearch(rawQ).split(/\s+/).filter(Boolean)
    rows = rows.filter((row) => {
      const hay = normalizeSearch(articleSearchText(row))
      return tokens.every((t) => hay.includes(t))
    })
  }

  rows.sort((a, b) => {
    switch (sortKey.value) {
      case 'created_desc':
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      case 'sold_desc':
        return (b.sold_at || '').localeCompare(a.sold_at || '')
      case 'purchase_asc':
        return a.purchase_price - b.purchase_price
      case 'purchase_desc':
        return b.purchase_price - a.purchase_price
      default:
        return 0
    }
  })
  return rows
})

watch([filterSold, sortKey, searchQuery, pageSize], () => {
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

watch([filterSold, sortKey, searchQuery, pageSize], () => {
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
