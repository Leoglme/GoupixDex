<template>
  <UCard
    class="app-card-bleed-md overflow-hidden"
    :ui="{
      header: 'px-4 sm:px-6 pt-6 pb-3 border-b border-[var(--app-line)]',
      body: 'p-0 sm:p-0',
    }"
  >
    <template #header>
      <div>
        <p class="text-sm font-medium text-[var(--app-ink)]">{{ title }}</p>
        <p class="text-xs text-[var(--app-ink-soft)]">{{ subtitle }}</p>
      </div>
    </template>

    <div v-if="sortedSales.length" :class="maxHeightClass">
      <GoupixDexBaseTable min-width="720px">
        <template #head>
          <GoupixDexBaseTableTh>Date</GoupixDexBaseTableTh>
          <GoupixDexBaseTableTh>Article</GoupixDexBaseTableTh>
          <GoupixDexBaseTableTh>Canal</GoupixDexBaseTableTh>
          <GoupixDexBaseTableTh align="right">Achat</GoupixDexBaseTableTh>
          <GoupixDexBaseTableTh align="right">Prix affiché</GoupixDexBaseTableTh>
          <GoupixDexBaseTableTh align="right">Prix réalisé</GoupixDexBaseTableTh>
          <GoupixDexBaseTableTh align="right">Marge</GoupixDexBaseTableTh>
          <GoupixDexBaseTableTh align="center" sr-only>Ouvrir</GoupixDexBaseTableTh>
        </template>

        <GoupixDexBaseTableTr v-for="r in sortedSales" :key="r.article_id">
          <GoupixDexBaseTableTd label="Date" class="whitespace-nowrap text-[var(--app-ink-soft)]">
            {{ formatDate(r.sold_at) }}
          </GoupixDexBaseTableTd>
          <GoupixDexBaseTableTd label="Article" class="max-w-[280px]">
            <span class="block truncate font-medium text-[var(--app-ink)]">{{ r.title }}</span>
          </GoupixDexBaseTableTd>
          <GoupixDexBaseTableTd label="Canal">
            <span
              v-if="r.sale_source && SOURCE_STYLES[r.sale_source]"
              class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
              :style="{
                backgroundColor: SOURCE_STYLES[r.sale_source].bg,
                color: SOURCE_STYLES[r.sale_source].text,
              }"
            >
              {{ SOURCE_STYLES[r.sale_source].label }}
            </span>
            <span v-else class="text-[var(--app-faint)]">—</span>
          </GoupixDexBaseTableTd>
          <GoupixDexBaseTableTd label="Achat" align="right" class="tabular-nums">
            {{ eur.format(r.purchase_price_eur) }}
          </GoupixDexBaseTableTd>
          <GoupixDexBaseTableTd label="Prix affiché" align="right" class="text-[var(--app-ink-soft)] tabular-nums">
            {{ r.listing_price_eur != null ? eur.format(r.listing_price_eur) : '—' }}
          </GoupixDexBaseTableTd>
          <GoupixDexBaseTableTd label="Prix réalisé" align="right" class="font-medium tabular-nums">
            {{ r.realized_price_eur != null ? eur.format(r.realized_price_eur) : '—' }}
          </GoupixDexBaseTableTd>
          <GoupixDexBaseTableTd
            label="Marge"
            align="right"
            class="font-semibold text-[var(--app-accent-ink)] tabular-nums"
          >
            {{ eur.format(r.profit_eur) }}
          </GoupixDexBaseTableTd>
          <GoupixDexBaseTableTd label="Fiche" align="center" class="goupix-card-table__actions">
            <UButton
              :to="`/articles/${r.article_id}`"
              size="xs"
              color="neutral"
              variant="ghost"
              icon="i-lucide-external-link"
              square
              @click="(e: MouseEvent) => openArticleFromClick(r.article_id, e)"
            />
          </GoupixDexBaseTableTd>
        </GoupixDexBaseTableTr>
      </GoupixDexBaseTable>
    </div>
    <p v-else class="px-4 py-8 text-center text-sm text-[var(--app-ink-soft)]">{{ emptyMessage }}</p>
  </UCard>
</template>

<script setup lang="ts">
import type { RecentSaleRow } from '~/composables/useStats'

const { openArticleFromClick } = useOpenArticleDrawer()

const props = withDefaults(
  defineProps<{
    sales: RecentSaleRow[]
    title?: string
    subtitle?: string
    emptyMessage?: string
    maxHeightClass?: string
  }>(),
  {
    title: 'Dernières ventes',
    subtitle: 'Les transactions les plus récentes en premier',
    emptyMessage: "Aucune vente pour l'instant.",
    maxHeightClass: 'max-h-96 overflow-auto',
  },
)

const eur = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const sortedSales = computed(() =>
  [...props.sales].sort((a, b) => {
    const ta = a.sold_at ? new Date(a.sold_at).getTime() : 0
    const tb = b.sold_at ? new Date(b.sold_at).getTime() : 0
    return tb - ta
  }),
)

/**
 * Format an ISO timestamp for the sales table (French locale).
 * @param raw - `sold_at` from API or null
 * @returns {string} Localized date/time or em dash
 */
function formatDate(raw: string | null): string {
  if (!raw) {
    return '—'
  }
  return new Date(raw).toLocaleString('fr-FR', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const SOURCE_STYLES: Record<'vinted' | 'ebay', { label: string; bg: string; text: string }> = {
  vinted: { label: 'Vinted', bg: 'rgb(0, 131, 143)', text: '#fff' },
  ebay: { label: 'eBay', bg: 'rgb(134, 184, 23)', text: '#fff' },
}
</script>
