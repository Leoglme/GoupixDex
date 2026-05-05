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
              { label: 'Cardmarket ↑', value: 'cm_asc' },
              { label: 'Cardmarket ↓', value: 'cm_desc' },
            ]"
            value-key="value"
            label-key="label"
            class="min-w-0 flex-1 sm:w-52 sm:flex-none"
          />
        </div>
        <p v-if="pricingLoading" class="text-muted text-sm sm:ml-auto md:ml-0 md:whitespace-nowrap">
          Chargement des prix PokéWallet…
        </p>
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
            <th class="border-default border-b px-3 py-2 font-medium">Cardmarket</th>
            <th class="border-default border-b px-3 py-2 font-medium">TCGPlayer</th>
            <th class="border-default border-b px-3 py-2 font-medium">Dates</th>
            <th class="border-default border-b px-3 py-2 text-end font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in filtered" :key="row.id" class="group border-default hover:bg-elevated/40 border-t">
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
                :src="row.images[0]?.image_url"
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
              {{ pricingById.get(row.id)?.set_name || row.set_code || '—' }}
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
              <UBadge :color="(row.published_on_vinted ?? false) ? 'success' : 'neutral'" variant="subtle">
                {{ (row.published_on_vinted ?? false) ? 'Oui' : 'Non' }}
              </UBadge>
            </td>
            <td v-if="showEbayColumn" class="border-default border-b px-3 py-3 align-middle">
              <UBadge :color="(row.published_on_ebay ?? false) ? 'success' : 'neutral'" variant="subtle">
                {{ (row.published_on_ebay ?? false) ? 'Oui' : 'Non' }}
              </UBadge>
            </td>
            <td class="border-default border-b px-3 py-3 align-middle">
              <span v-if="pricingById.get(row.id)?.cardmarket_eur != null">
                {{ eur.format(pricingById.get(row.id)!.cardmarket_eur!) }}
              </span>
              <span v-else class="text-muted">—</span>
            </td>
            <td class="border-default border-b px-3 py-3 align-middle">
              <span v-if="pricingById.get(row.id)?.tcgplayer_usd != null">
                {{ usd.format(pricingById.get(row.id)!.tcgplayer_usd!) }}
              </span>
              <span v-else class="text-muted">—</span>
            </td>
            <td class="text-muted border-default border-b px-3 py-3 align-middle text-xs whitespace-nowrap">
              <div>Créé le {{ new Date(row.created_at).toLocaleDateString('fr-FR') }}</div>
              <div v-if="row.sold_at">Vendu le {{ new Date(row.sold_at).toLocaleDateString('fr-FR') }}</div>
            </td>
            <td class="border-default border-b px-3 py-3 text-end align-middle">
              <UDropdownMenu
                :items="[
                  [
                    { label: 'Modifier', icon: 'i-lucide-pencil', onSelect: () => emit('edit', row.id) },
                    {
                      label: 'Mettre en ligne sur Vinted',
                      icon: 'i-lucide-store',
                      disabled: !isDesktopApp || row.is_sold || !row.images?.length,
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
                ]"
              >
                <UButton color="neutral" variant="ghost" icon="i-lucide-more-horizontal" square />
              </UDropdownMenu>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="space-y-3 lg:hidden">
      <div v-for="row in filtered" :key="row.id" class="w-full">
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
                  <img :src="row.images[0]!.image_url" :alt="row.title" class="h-20 w-full object-cover" />
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
                      Vinted {{ (row.published_on_vinted ?? false) ? 'oui' : 'non' }}
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
import type { Ref } from 'vue'
import type { Article } from '~/composables/useArticles'
import type { PricingLookup } from '~/composables/usePricing'
import type { ArticleListFilterSold, ArticleListSortKey } from '~/composables/useUiPrefsLocalStorage'
import { loadArticleListPrefs, saveArticleListPrefs } from '~/composables/useUiPrefsLocalStorage'

const props = defineProps<{
  articles: Article[]
  pricingById: Map<number, PricingLookup>
  loading?: boolean
  pricingLoading?: boolean
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
})

watch([filterSold, sortKey, searchQuery], () => {
  saveArticleListPrefs({
    filterSold: filterSold.value,
    sortKey: sortKey.value,
    searchQuery: searchQuery.value,
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
  const p = props.pricingById.get(row.id)
  return [row.pokemon_name, row.set_code, row.card_number, row.title, p?.set_name]
    .filter((x): x is string => Boolean(x && String(x).trim()))
    .join(' ')
}

const eur = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 2,
})
const usd = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 2,
})

const filtered = computed(() => {
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
    const pa = props.pricingById.get(a.id)
    const pb = props.pricingById.get(b.id)
    const cm = (p: PricingLookup | undefined) => p?.cardmarket_eur ?? -1
    switch (sortKey.value) {
      case 'created_desc':
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      case 'sold_desc':
        return (b.sold_at || '').localeCompare(a.sold_at || '')
      case 'purchase_asc':
        return a.purchase_price - b.purchase_price
      case 'purchase_desc':
        return b.purchase_price - a.purchase_price
      case 'cm_asc':
        return cm(pa) - cm(pb)
      case 'cm_desc':
        return cm(pb) - cm(pa)
      default:
        return 0
    }
  })
  return rows
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

const selectedRows = computed(() => props.articles.filter((a) => selectedIds.value.includes(a.id)))

const bulkVintedDisabledReason = computed(() => {
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

const bulkEbayDisabledReason = computed(() => {
  if (!props.ebayPublishAvailable) {
    return 'eBay n’est pas prêt (connexion OAuth et configuration des annonces).'
  }
  if (selectedRows.value.some((a) => !canBulkEbay(a))) {
    return 'Articles non vendus, pas déjà sur eBay, avec au moins une image en HTTPS.'
  }
  return ''
})

const bulkBothDisabledReason = computed(() => {
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

const showBulkVinted = computed(() => props.vintedChannelEnabled === true)
const showBulkEbay = computed(() => props.ebayPublishAvailable === true)
/** Shown when both channels are ready (disabled on web: see bulkBothDisabledReason). */
const showBulkBoth = computed(() => props.vintedChannelEnabled === true && props.ebayPublishAvailable === true)

const selectedCount = computed(() => selectedIds.value.length)

const allFilteredSelected = computed(
  () => filtered.value.length > 0 && filtered.value.every((r) => selectedIds.value.includes(r.id)),
)

const someFilteredSelected = computed(() => filtered.value.some((r) => selectedIds.value.includes(r.id)))

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
  const fids = filtered.value.map((r) => r.id)
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

const UAvatar = resolveComponent('UAvatar')
</script>
