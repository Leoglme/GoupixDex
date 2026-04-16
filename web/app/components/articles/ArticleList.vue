<script setup lang="ts">
import type { Article } from '~/composables/useArticles'
import type { PricingLookup } from '~/composables/usePricing'

const props = defineProps<{
  articles: Article[]
  pricingById: Map<number, PricingLookup>
  loading?: boolean
  pricingLoading?: boolean
}>()

const emit = defineEmits<{
  edit: [id: number]
  delete: [id: number]
  sold: [article: Article]
  'publish-vinted': [article: Article]
  'bulk-delete': [ids: number[]]
}>()

const filterSold = ref<'all' | 'sold' | 'unsold'>('all')
const sortKey = ref<'created_desc' | 'sold_desc' | 'purchase_asc' | 'purchase_desc' | 'cm_asc' | 'cm_desc'>('created_desc')
/** Filtre texte : Pokémon, code set, série (nom extension), n°, titre. */
const searchQuery = ref('')
const { isDesktopApp } = useDesktopRuntime()

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

/** Sélection multi-lignes (ids visibles dans la liste courante) */
const selectedIds = ref<number[]>([])

watch(
  () => props.articles.map(a => a.id).sort((a, b) => a - b).join(','),
  () => {
    const valid = new Set(props.articles.map(a => a.id))
    selectedIds.value = selectedIds.value.filter(id => valid.has(id))
  }
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
      title="Mise en ligne Vinted disponible uniquement dans l’app desktop"
    >
      <template #description>
        <p class="text-sm leading-relaxed">
          Installez GoupixDex sur Windows ou macOS pour publier depuis votre connexion, comme sur la page
          <NuxtLink
            to="/downloads"
            class="font-medium text-primary underline decoration-primary/40 underline-offset-2 hover:decoration-primary"
          >
            Télécharger l’app
          </NuxtLink>
          (installateurs et conseils pour choisir le bon fichier).
        </p>
      </template>
    </UAlert>

    <!-- Recherche à gauche, filtres à droite (md+) ; colonne sur très petit écran -->
    <div
      class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between md:gap-4"
    >
      <UInput
        v-model="searchQuery"
        icon="i-lucide-search"
        placeholder="Rechercher : Pokémon, set, série, n°…"
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
          size="sm"
          color="error"
          icon="i-lucide-trash-2"
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
              Pokémon
            </th>
            <th class="px-3 py-2 font-medium border-b border-default">
              Série / set
            </th>
            <th class="px-3 py-2 font-medium border-b border-default">
              N°
            </th>
            <th class="px-3 py-2 font-medium border-b border-default">
              Achat
            </th>
            <th class="px-3 py-2 font-medium border-b border-default">
              Cardmarket
            </th>
            <th class="px-3 py-2 font-medium border-b border-default">
              TCGPlayer
            </th>
            <th class="px-3 py-2 font-medium border-b border-default">
              Vendu
            </th>
            <th class="px-3 py-2 font-medium border-b border-default">
              Vinted
            </th>
            <th class="px-3 py-2 font-medium border-b border-default">
              Vente
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
            <td class="px-3 py-3 align-middle border-b border-default">
              <UBadge
                :color="row.is_sold ? 'success' : 'error'"
                variant="subtle"
              >
                {{ row.is_sold ? 'Oui' : 'Non' }}
              </UBadge>
            </td>
            <td class="px-3 py-3 align-middle border-b border-default">
              <UBadge
                :color="(row.published_on_vinted ?? false) ? 'success' : 'neutral'"
                variant="subtle"
              >
                {{ (row.published_on_vinted ?? false) ? 'Oui' : 'Non' }}
              </UBadge>
            </td>
            <td class="px-3 py-3 align-middle border-b border-default">
              {{ row.sell_price != null ? eur.format(row.sell_price) : '—' }}
            </td>
            <td class="px-3 py-3 text-muted text-xs whitespace-nowrap align-middle border-b border-default">
              <div>C : {{ new Date(row.created_at).toLocaleDateString('fr-FR') }}</div>
              <div v-if="row.sold_at">
                V : {{ new Date(row.sold_at).toLocaleDateString('fr-FR') }}
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
                      :color="row.is_sold ? 'success' : 'error'"
                      variant="subtle"
                    >
                      {{ row.is_sold ? 'Vendu' : 'En stock' }}
                    </UBadge>
                    <UBadge
                      :color="(row.published_on_vinted ?? false) ? 'success' : 'neutral'"
                      variant="subtle"
                    >
                      Vinted {{ (row.published_on_vinted ?? false) ? 'oui' : 'non' }}
                    </UBadge>
                    <span class="text-muted">
                      Achat {{ eur.format(row.purchase_price) }}
                    </span>
                    <span class="text-muted">
                      Vente {{ row.sell_price != null ? eur.format(row.sell_price) : '—' }}
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
