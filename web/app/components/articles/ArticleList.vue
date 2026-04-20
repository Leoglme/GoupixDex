<script setup lang="ts">
import type { Article } from '~/composables/useArticles'
import type { PricingLookup } from '~/composables/usePricing'
import {
  loadArticleListPrefs,
  saveArticleListPrefs,
  type ArticleListFilterSold,
  type ArticleListSortKey
} from '~/composables/useUiPrefsLocalStorage'

const props = defineProps<{
  articles: Article[]
  pricingById: Map<number, PricingLookup>
  loading?: boolean
  pricingLoading?: boolean
  /** Show the “listed on eBay” column (same gate as eBay publish actions). */
  showEbayColumn?: boolean
  /** eBay enabled + account connected + listing wizard complete (settings); hides eBay actions otherwise. */
  ebayPublishAvailable?: boolean
  /** Vinted activé dans Paramètres → marchés (sinon l’API refuse la publication). */
  vintedChannelEnabled?: boolean
  /** Désactive les boutons de mise en ligne groupée pendant un appel API. */
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

function ebayRowDisabled(row: Article) {
  return row.is_sold || (row.published_on_ebay ?? false) || !(row.images?.length)
}

function hasHttpsImage(row: Article) {
  return row.images?.some(img => (img.image_url || '').startsWith('https://')) ?? false
}

function canBulkVinted(row: Article) {
  return !row.is_sold && (row.images?.length ?? 0) > 0
}

function canBulkEbay(row: Article) {
  return !row.is_sold && !(row.published_on_ebay ?? false) && hasHttpsImage(row)
}

function soldStatusLabel(row: Article) {
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

function soldStatusBrandStyle(row: Article): { backgroundColor: string, color: string } | null {
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

const filterSold = ref<ArticleListFilterSold>('unsold')
const sortKey = ref<ArticleListSortKey>('created_desc')
/** Text filter: name, set code, set name, card #, title. */
const searchQuery = ref('')

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
    searchQuery: searchQuery.value
  })
})

function normalizeSearch(s: string) {
  return s
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
}

function articleSearchText(row: Article) {
  const p = props.pricingById.get(row.id)
  return [
    row.pokemon_name,
    row.set_code,
    row.card_number,
    row.title,
    p?.set_name,
  ]
    .filter((x): x is string => Boolean(x && String(x).trim()))
    .join(' ')
}

const eur = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 2
})
const usd = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 2
})

const filtered = computed(() => {
  let rows = [...props.articles]
  if (filterSold.value === 'sold') {
    rows = rows.filter(r => r.is_sold)
  } else if (filterSold.value === 'unsold') {
    rows = rows.filter(r => !r.is_sold)
  }

  const rawQ = searchQuery.value.trim()
  if (rawQ) {
    const tokens = normalizeSearch(rawQ)
      .split(/\s+/)
      .filter(Boolean)
    rows = rows.filter((row) => {
      const hay = normalizeSearch(articleSearchText(row))
      return tokens.every(t => hay.includes(t))
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
const selectedIds = ref<number[]>([])

watch(
  () => props.articles.map(a => a.id).sort((a, b) => a - b).join(','),
  () => {
    const valid = new Set(props.articles.map(a => a.id))
    selectedIds.value = selectedIds.value.filter(id => valid.has(id))
  }
)

const selectedRows = computed(() =>
  props.articles.filter(a => selectedIds.value.includes(a.id))
)

const bulkVintedDisabledReason = computed(() => {
  if (!props.vintedChannelEnabled) {
    return 'Activez Vinted dans les paramètres marché.'
  }
  if (!isDesktopApp.value) {
    return 'La publication Vinted groupée nécessite l’application desktop.'
  }
  if (selectedRows.value.some(a => !canBulkVinted(a))) {
    return 'Tous les articles sélectionnés doivent être non vendus et avoir au moins une photo.'
  }
  return ''
})

const bulkEbayDisabledReason = computed(() => {
  if (!props.ebayPublishAvailable) {
    return 'eBay n’est pas prêt (connexion OAuth et configuration des annonces).'
  }
  if (selectedRows.value.some(a => !canBulkEbay(a))) {
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
  if (selectedRows.value.some(a => !canBulkVinted(a) || !canBulkEbay(a))) {
    return 'Chaque article doit être éligible à la fois pour Vinted (photos) et pour eBay (HTTPS, pas déjà publié).'
  }
  return ''
})

const showBulkVinted = computed(() => props.vintedChannelEnabled === true)
const showBulkEbay = computed(() => props.ebayPublishAvailable === true)
const showBulkBoth = computed(
  () =>
    props.vintedChannelEnabled === true
    && props.ebayPublishAvailable === true
    && isDesktopApp.value
)

const selectedCount = computed(() => selectedIds.value.length)

const allFilteredSelected = computed(
  () =>
    filtered.value.length > 0
    && filtered.value.every(r => selectedIds.value.includes(r.id))
)

const someFilteredSelected = computed(() =>
  filtered.value.some(r => selectedIds.value.includes(r.id))
)

function isSelected(id: number) {
  return selectedIds.value.includes(id)
}

function toggleId(id: number, checked: boolean | 'indeterminate') {
  if (checked === 'indeterminate') {
    return
  }
  if (checked) {
    if (!selectedIds.value.includes(id)) {
      selectedIds.value = [...selectedIds.value, id]
    }
  } else {
    selectedIds.value = selectedIds.value.filter(i => i !== id)
  }
}

function toggleSelectAll(checked: boolean | 'indeterminate') {
  if (checked === 'indeterminate') {
    return
  }
  const fids = filtered.value.map(r => r.id)
  if (checked) {
    const s = new Set(selectedIds.value)
    fids.forEach(id => s.add(id))
    selectedIds.value = [...s]
  } else {
    const rm = new Set(fids)
    selectedIds.value = selectedIds.value.filter(id => !rm.has(id))
  }
}

function clearSelection() {
  selectedIds.value = []
}

const UAvatar = resolveComponent('UAvatar')
</script>

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
            class="font-medium text-primary underline decoration-primary/40 underline-offset-2 hover:decoration-primary"
          >
            Télécharger l'app
          </NuxtLink>
          (installateurs et conseils pour choisir le bon fichier).
        </p>
      </template>
    </UAlert>

    <!-- Search left, filters right (md+); stacked on very small screens -->
    <div
      class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between md:gap-4"
    >
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
              { label: 'Vendus', value: 'sold' }
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
              { label: 'Cardmarket ↓', value: 'cm_desc' }
            ]"
            value-key="value"
            label-key="label"
            class="min-w-0 flex-1 sm:w-52 sm:flex-none"
          />
        </div>
        <p
          v-if="pricingLoading"
          class="text-sm text-muted sm:ml-auto md:ml-0 md:whitespace-nowrap"
        >
          Chargement des prix PokéWallet…
        </p>
      </div>
    </div>

    <div
      v-if="selectedCount > 0"
      class="flex flex-col gap-2 rounded-lg border border-default bg-elevated/60 px-3 py-2.5 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between"
    >
      <p class="text-sm text-highlighted">
        {{ selectedCount }} article{{ selectedCount > 1 ? 's' : '' }} sélectionné{{ selectedCount > 1 ? 's' : '' }}
      </p>
      <div class="flex flex-wrap gap-2">
        <UButton size="sm" color="neutral" variant="outline" @click="clearSelection">
          Tout désélectionner
        </UButton>
        <UButton
          v-if="showBulkVinted"
          size="sm"
          color="primary"
          variant="subtle"
          icon="i-lucide-store"
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
          color="primary"
          variant="subtle"
          icon="i-lucide-shopping-bag"
          :disabled="!!bulkEbayDisabledReason || bulkPublishing"
          :title="bulkEbayDisabledReason || undefined"
          :loading="bulkPublishing"
          @click="emit('bulk-publish-ebay', [...selectedIds])"
        >
          Mettre en ligne sur eBay
        </UButton>
        <UButton
          v-if="showBulkBoth"
          size="sm"
          color="primary"
          icon="i-lucide-upload-cloud"
          :disabled="!!bulkBothDisabledReason || bulkPublishing"
          :title="bulkBothDisabledReason || undefined"
          :loading="bulkPublishing"
          @click="emit('bulk-publish-both', [...selectedIds])"
        >
          Mettre en ligne (eBay + Vinted)
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

    <div class="hidden lg:block overflow-x-auto rounded-lg ring ring-default">
      <table class="min-w-full text-sm border-separate border-spacing-0">
        <thead class="bg-elevated/60 text-left text-muted uppercase text-xs">
          <tr>
            <th class="w-10 px-3 py-2 font-medium align-middle border-b border-default">
              <UCheckbox
                :model-value="allFilteredSelected"
                :indeterminate="someFilteredSelected && !allFilteredSelected"
                aria-label="Tout sélectionner sur cette page"
                @update:model-value="toggleSelectAll"
              />
            </th>
            <th class="w-12 px-3 py-2 font-medium border-b border-default" />
            <th class="px-3 py-2 font-medium border-b border-default">
              Nom de l'article
            </th>
            <th class="px-3 py-2 font-medium border-b border-default">
              Vendu
            </th>
            <th class="px-3 py-2 font-medium border-b border-default">
              Série / set
            </th>
            <th class="px-3 py-2 font-medium border-b border-default">
              N°
            </th>
            <th class="px-3 py-2 font-medium border-b border-default">
              Prix d'achat
            </th>
            <th class="px-3 py-2 font-medium border-b border-default">
              Prix de vente
            </th>
            <th class="px-3 py-2 font-medium border-b border-default">
              Prix réalisé
            </th>
            <th class="px-3 py-2 font-medium border-b border-default">
              Vinted
            </th>
            <th
              v-if="showEbayColumn"
              class="px-3 py-2 font-medium border-b border-default"
            >
              eBay
            </th>
            <th class="px-3 py-2 font-medium border-b border-default">
              Cardmarket
            </th>
            <th class="px-3 py-2 font-medium border-b border-default">
              TCGPlayer
            </th>
            <th class="px-3 py-2 font-medium border-b border-default">
              Dates
            </th>
            <th class="px-3 py-2 font-medium text-end border-b border-default">
              Actions
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in filtered"
            :key="row.id"
            class="border-t border-default hover:bg-elevated/40"
          >
            <td class="px-3 py-3 align-middle border-b border-default">
              <UCheckbox
                :model-value="isSelected(row.id)"
                :aria-label="`Sélectionner ${row.pokemon_name || row.title}`"
                @update:model-value="(v) => toggleId(row.id, v)"
              />
            </td>
            <td class="px-3 py-3 align-middle border-b border-default">
              <UAvatar
                v-if="row.images?.length"
                size="lg"
                :src="row.images[0]?.image_url"
                :alt="row.title"
                class="ring-1 ring-default/80"
              />
              <div
                v-else
                class="flex size-9 items-center justify-center rounded-full bg-elevated text-xs text-muted"
              >
                {{ (row.pokemon_name || row.title || '?').slice(0, 2).toUpperCase() }}
              </div>
            </td>
            <td class="px-3 py-3 font-medium text-highlighted align-middle border-b border-default">
              <div class="flex flex-col gap-0.5">
                <span class="truncate">
                  {{ row.pokemon_name || row.title || '—' }}
                </span>
                <span class="text-xs text-muted truncate">
                  {{ row.title }}
                </span>
              </div>
            </td>
            <td class="px-3 py-3 align-middle border-b border-default">
              <UBadge
                v-if="!row.is_sold"
                color="error"
                variant="subtle"
                class="max-w-[10rem] whitespace-normal text-center leading-snug"
              >
                {{ soldStatusLabel(row) }}
              </UBadge>
              <span
                v-else-if="soldStatusBrandStyle(row)"
                class="inline-flex max-w-[10rem] whitespace-normal rounded-md px-2 py-0.5 text-center text-xs font-semibold leading-snug ring-1 ring-black/10"
                :style="soldStatusBrandStyle(row)!"
              >
                {{ soldStatusLabel(row) }}
              </span>
              <UBadge
                v-else
                color="success"
                variant="subtle"
                class="max-w-[10rem] whitespace-normal text-center leading-snug"
              >
                {{ soldStatusLabel(row) }}
              </UBadge>
            </td>
            <td class="px-3 py-3 text-muted align-middle border-b border-default">
              {{ pricingById.get(row.id)?.set_name || row.set_code || '—' }}
            </td>
            <td class="px-3 py-3 align-middle border-b border-default">
              {{ row.card_number || '—' }}
            </td>
            <td class="px-3 py-3 align-middle border-b border-default">
              {{ eur.format(row.purchase_price) }}
            </td>
            <td class="px-3 py-3 align-middle border-b border-default">
              {{ row.sell_price != null ? eur.format(row.sell_price) : '—' }}
            </td>
            <td class="px-3 py-3 align-middle border-b border-default">
              <span v-if="realizedSalePrice(row) != null">
                {{ eur.format(realizedSalePrice(row)!) }}
              </span>
              <span v-else class="text-muted">—</span>
            </td>
            <td class="px-3 py-3 align-middle border-b border-default">
              <UBadge
                :color="(row.published_on_vinted ?? false) ? 'success' : 'neutral'"
                variant="subtle"
              >
                {{ (row.published_on_vinted ?? false) ? 'Oui' : 'Non' }}
              </UBadge>
            </td>
            <td
              v-if="showEbayColumn"
              class="px-3 py-3 align-middle border-b border-default"
            >
              <UBadge
                :color="(row.published_on_ebay ?? false) ? 'success' : 'neutral'"
                variant="subtle"
              >
                {{ (row.published_on_ebay ?? false) ? 'Oui' : 'Non' }}
              </UBadge>
            </td>
            <td class="px-3 py-3 align-middle border-b border-default">
              <span v-if="pricingById.get(row.id)?.cardmarket_eur != null">
                {{ eur.format(pricingById.get(row.id)!.cardmarket_eur!) }}
              </span>
              <span v-else class="text-muted">—</span>
            </td>
            <td class="px-3 py-3 align-middle border-b border-default">
              <span v-if="pricingById.get(row.id)?.tcgplayer_usd != null">
                {{ usd.format(pricingById.get(row.id)!.tcgplayer_usd!) }}
              </span>
              <span v-else class="text-muted">—</span>
            </td>
            <td class="px-3 py-3 text-muted text-xs whitespace-nowrap align-middle border-b border-default">
              <div>Créé le {{ new Date(row.created_at).toLocaleDateString('fr-FR') }}</div>
              <div v-if="row.sold_at">
                Vendu le {{ new Date(row.sold_at).toLocaleDateString('fr-FR') }}
              </div>
            </td>
            <td class="px-3 py-3 text-end align-middle border-b border-default">
              <UDropdownMenu
                :items="[[
                  { label: 'Modifier', icon: 'i-lucide-pencil', onSelect: () => emit('edit', row.id) },
                  {
                    label: 'Mettre en ligne sur Vinted',
                    icon: 'i-lucide-store',
                    disabled: !isDesktopApp || row.is_sold || !(row.images?.length),
                    onSelect: () => emit('publish-vinted', row)
                  },
                  ...(props.ebayPublishAvailable
                    ? [
                        {
                          label: 'Mettre en ligne sur eBay',
                          icon: 'i-lucide-shopping-bag',
                          disabled: ebayRowDisabled(row),
                          onSelect: () => emit('publish-ebay', row)
                        }
                      ]
                    : []),
                  { label: 'Marquer vendu', icon: 'i-lucide-circle-check', disabled: row.is_sold, onSelect: () => emit('sold', row) },
                  { label: 'Supprimer', icon: 'i-lucide-trash-2', color: 'error', onSelect: () => emit('delete', row.id) }
                ]]"
              >
                <UButton
                  color="neutral"
                  variant="ghost"
                  icon="i-lucide-more-horizontal"
                  square
                />
              </UDropdownMenu>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="lg:hidden space-y-3">
      <div
        v-for="row in filtered"
        :key="row.id"
        class="w-full"
      >
        <UCard class="w-full border border-default/80 bg-elevated/70" :ui="{ body: 'p-3 space-y-3' }">
          <div class="flex items-start gap-3">
            <div class="pt-1 shrink-0">
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
                  class="w-20 shrink-0 rounded-lg overflow-hidden bg-elevated ring ring-default"
                >
                  <img
                    :src="row.images[0]!.image_url"
                    :alt="row.title"
                    class="w-full h-20 object-cover"
                  >
                </div>
                <div class="min-w-0 flex-1 space-y-1">
                  <p class="font-medium text-highlighted truncate">
                    {{ row.pokemon_name || row.title }}
                  </p>
                  <p class="text-xs text-muted truncate">
                    {{ row.set_code || '—' }} · {{ row.card_number || '—' }}
                  </p>
                  <div class="flex flex-wrap gap-1.5 text-[11px]">
                    <UBadge
                      v-if="!row.is_sold"
                      color="error"
                      variant="subtle"
                    >
                      {{ soldStatusLabel(row) }}
                    </UBadge>
                    <span
                      v-else-if="soldStatusBrandStyle(row)"
                      class="inline-flex rounded-md px-1.5 py-0.5 font-semibold ring-1 ring-black/10"
                      :style="soldStatusBrandStyle(row)!"
                    >
                      {{ soldStatusLabel(row) }}
                    </span>
                    <UBadge
                      v-else
                      color="success"
                      variant="subtle"
                    >
                      {{ soldStatusLabel(row) }}
                    </UBadge>
                    <UBadge
                      :color="(row.published_on_vinted ?? false) ? 'success' : 'neutral'"
                      variant="subtle"
                    >
                      Vinted {{ (row.published_on_vinted ?? false) ? 'oui' : 'non' }}
                    </UBadge>
                    <UBadge
                      v-if="showEbayColumn"
                      :color="(row.published_on_ebay ?? false) ? 'success' : 'neutral'"
                      variant="subtle"
                    >
                      eBay {{ (row.published_on_ebay ?? false) ? 'oui' : 'non' }}
                    </UBadge>
                    <span class="text-muted">
                      Achat {{ eur.format(row.purchase_price) }}
                    </span>
                    <span class="text-muted">
                      Prix affiché {{ row.sell_price != null ? eur.format(row.sell_price) : '—' }}
                    </span>
                    <span
                      v-if="row.is_sold"
                      class="text-muted"
                    >
                      Réalisé {{ realizedSalePrice(row) != null ? eur.format(realizedSalePrice(row)!) : '—' }}
                    </span>
                  </div>
                </div>
              </div>
              <div class="flex flex-wrap gap-2 justify-end">
                <UButton
                  size="sm"
                  variant="outline"
                  @click="emit('edit', row.id)"
                >
                  Modifier
                </UButton>
                <UButton
                  size="sm"
                  variant="outline"
                  icon="i-lucide-store"
                  :disabled="!isDesktopApp || row.is_sold || !(row.images?.length)"
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
                  size="sm"
                  :disabled="row.is_sold"
                  @click="emit('sold', row)"
                >
                  Vendu
                </UButton>
                <UButton
                  size="sm"
                  color="error"
                  variant="soft"
                  @click="emit('delete', row.id)"
                >
                  Supprimer
                </UButton>
              </div>
            </div>
          </div>
        </UCard>
      </div>
    </div>

    <div v-if="!loading && !filtered.length" class="text-center text-muted py-12">
      {{
        searchQuery.trim()
          ? 'Aucun résultat pour cette recherche.'
          : 'Aucun article.'
      }}
    </div>
  </div>
</template>
