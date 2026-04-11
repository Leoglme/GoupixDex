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
}>()

const filterSold = ref<'all' | 'sold' | 'unsold'>('all')
const sortKey = ref<'created_desc' | 'sold_desc' | 'purchase_asc' | 'purchase_desc' | 'cm_asc' | 'cm_desc'>('created_desc')

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
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between">
      <div class="flex flex-wrap gap-2">
        <USelect
          v-model="filterSold"
          :items="[
            { label: 'Tous', value: 'all' },
            { label: 'En stock', value: 'unsold' },
            { label: 'Vendus', value: 'sold' }
          ]"
          value-key="value"
          label-key="label"
          class="w-44"
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
          class="w-52"
        />
      </div>
      <p v-if="pricingLoading" class="text-sm text-muted">
        Chargement des prix PokéWallet…
      </p>
    </div>

    <div class="hidden lg:block overflow-x-auto rounded-lg ring ring-default">
      <table class="min-w-full text-sm">
        <thead class="bg-elevated text-left text-muted uppercase text-xs">
          <tr>
            <th class="px-3 py-2 font-medium">
              Pokémon
            </th>
            <th class="px-3 py-2 font-medium">
              Série / set
            </th>
            <th class="px-3 py-2 font-medium">
              N°
            </th>
            <th class="px-3 py-2 font-medium">
              Achat
            </th>
            <th class="px-3 py-2 font-medium">
              Suggéré (marge)
            </th>
            <th class="px-3 py-2 font-medium">
              Cardmarket
            </th>
            <th class="px-3 py-2 font-medium">
              TCGPlayer
            </th>
            <th class="px-3 py-2 font-medium">
              Vendu
            </th>
            <th class="px-3 py-2 font-medium">
              Vente
            </th>
            <th class="px-3 py-2 font-medium">
              Dates
            </th>
            <th class="px-3 py-2 font-medium text-end">
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
            <td class="px-3 py-2 font-medium text-highlighted">
              {{ row.pokemon_name || '—' }}
            </td>
            <td class="px-3 py-2 text-muted">
              {{ pricingById.get(row.id)?.set_name || row.set_code || '—' }}
            </td>
            <td class="px-3 py-2">
              {{ row.card_number || '—' }}
            </td>
            <td class="px-3 py-2">
              {{ eur.format(row.purchase_price) }}
            </td>
            <td class="px-3 py-2">
              <span v-if="pricingById.get(row.id)?.suggested_price_eur != null">
                {{ eur.format(pricingById.get(row.id)!.suggested_price_eur!) }}
              </span>
              <span v-else class="text-muted">—</span>
            </td>
            <td class="px-3 py-2">
              <span v-if="pricingById.get(row.id)?.cardmarket_eur != null">
                {{ eur.format(pricingById.get(row.id)!.cardmarket_eur!) }}
              </span>
              <span v-else class="text-muted">—</span>
            </td>
            <td class="px-3 py-2">
              <span v-if="pricingById.get(row.id)?.tcgplayer_usd != null">
                {{ usd.format(pricingById.get(row.id)!.tcgplayer_usd!) }}
              </span>
              <span v-else class="text-muted">—</span>
            </td>
            <td class="px-3 py-2">
              <UBadge
                :color="row.is_sold ? 'neutral' : 'primary'"
                variant="subtle"
              >
                {{ row.is_sold ? 'Oui' : 'Non' }}
              </UBadge>
            </td>
            <td class="px-3 py-2">
              {{ row.sell_price != null ? eur.format(row.sell_price) : '—' }}
            </td>
            <td class="px-3 py-2 text-muted text-xs whitespace-nowrap">
              <div>C : {{ new Date(row.created_at).toLocaleDateString('fr-FR') }}</div>
              <div v-if="row.sold_at">
                V : {{ new Date(row.sold_at).toLocaleDateString('fr-FR') }}
              </div>
            </td>
            <td class="px-3 py-2 text-end">
              <UDropdownMenu
                :items="[[
                  { label: 'Modifier', icon: 'i-lucide-pencil', onSelect: () => emit('edit', row.id) },
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

    <div class="lg:hidden space-y-4">
      <div
        v-for="row in filtered"
        :key="row.id"
        class="space-y-2"
      >
        <ArticleCard
          :article="row"
          :pricing="pricingById.get(row.id)"
        />
        <div class="flex flex-wrap gap-2 justify-end">
          <UButton size="sm" variant="outline" @click="emit('edit', row.id)">
            Modifier
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

    <div v-if="!loading && !filtered.length" class="text-center text-muted py-12">
      Aucun article.
    </div>
  </div>
</template>
