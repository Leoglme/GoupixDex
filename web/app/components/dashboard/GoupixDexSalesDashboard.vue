<template>
  <div class="space-y-6">
    <div class="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
      <GoupixDexStatsCard
        title="Chiffre d'affaires"
        :value="roundedEuroFormatter.format(props.stats.revenue_period_eur)"
        :trend-percent="revenueTrendPercent"
        :description="revenueDescription"
        icon="i-lucide-coins"
        is-compact-on-mobile
      />
      <GoupixDexStatsCard
        title="Bénéfice"
        :value="roundedEuroFormatter.format(props.stats.profit_period_eur)"
        :trend-percent="profitTrendPercent"
        :description="profitDescription"
        icon="i-lucide-trending-up"
        is-compact-on-mobile
      />
      <GoupixDexStatsCard
        title="Ventes"
        :value="numberFormatter.format(props.stats.period_sales_count)"
        :trend-percent="salesCountTrendPercent"
        :description="salesCountDescription"
        icon="i-lucide-shopping-bag"
        is-compact-on-mobile
      />
      <GoupixDexStatsCard
        title="Délai de vente"
        :value="props.stats.median_hours_to_sell === null ? '—' : formatDurationHours(props.stats.median_hours_to_sell)"
        description="médiane, de l'ajout à la vente"
        icon="i-lucide-timer"
        is-compact-on-mobile
      />
    </div>

    <div class="grid gap-6 lg:grid-cols-3">
      <GoupixDexDashboardSalesChart
        class="lg:col-span-2"
        :points="props.stats.sales_timeline"
        :period="props.stats.range.period"
      />
      <GoupixDexDashboardSaleChannels :channels="props.stats.sales_by_channel" />
    </div>

    <div class="grid gap-6 lg:grid-cols-2">
      <UCard :ui="{ body: 'p-4' }">
        <div class="mb-3 flex items-center justify-between gap-2">
          <h2 class="text-highlighted flex items-center gap-1.5 text-sm font-semibold">
            Dernières ventes
            <span v-if="props.stats.period_sales_count" class="text-muted font-normal tabular-nums">
              ({{ numberFormatter.format(props.stats.period_sales_count) }})
            </span>
          </h2>
          <NuxtLink
            to="/articles/sold"
            class="text-muted hover:text-highlighted inline-flex shrink-0 items-center gap-1 text-xs font-medium transition-colors"
          >
            Toutes <UIcon name="i-lucide-arrow-right" class="size-3" />
          </NuxtLink>
        </div>
        <div v-if="props.stats.recent_sales.length" class="divide-y divide-[var(--app-line-soft)]">
          <GoupixDexDashboardArticleRow
            v-for="sale in props.stats.recent_sales"
            :key="sale.article_id"
            :article-id="sale.article_id"
            :title="sale.title"
            :pokemon-name="sale.pokemon_name"
            :image-url="sale.image_url"
          >
            <template #subtitle>
              <GoupixDexMarketplaceAppIcon v-if="sale.sale_source" :marketplace="sale.sale_source" is-small />
              <span class="truncate">{{ formatSaleDate(sale.sold_at) }}</span>
            </template>
            <template #trailing>
              <span class="text-highlighted block text-sm font-semibold">{{
                formatPrice(sale.realized_price_eur)
              }}</span>
              <span
                class="block text-xs font-semibold"
                :class="sale.profit_eur >= 0 ? 'text-(--app-green)' : 'text-(--app-red)'"
              >
                {{ formatSignedPrice(sale.profit_eur) }}
              </span>
            </template>
          </GoupixDexDashboardArticleRow>
        </div>
        <p v-else class="text-muted py-6 text-center text-sm">Aucune vente sur cette période.</p>
      </UCard>

      <UCard :ui="{ body: 'p-4' }">
        <div class="mb-3 flex items-center justify-between gap-2">
          <h2 class="text-highlighted text-sm font-semibold">Cartes les plus rentables</h2>
          <span v-if="topProfitableShareLabel" class="shrink-0 text-xs font-semibold text-(--app-green) tabular-nums">
            {{ topProfitableShareLabel }}
          </span>
        </div>
        <div v-if="props.stats.top_profitable.length" class="divide-y divide-[var(--app-line-soft)]">
          <GoupixDexDashboardArticleRow
            v-for="sale in props.stats.top_profitable"
            :key="sale.article_id"
            :article-id="sale.article_id"
            :title="sale.title"
            :pokemon-name="sale.pokemon_name"
            :image-url="sale.image_url"
          >
            <template #subtitle>
              <span class="truncate tabular-nums">
                {{ formatPrice(sale.purchase_price_eur) }} → {{ formatPrice(sale.realized_price_eur) }}
              </span>
            </template>
            <template #trailing>
              <span
                class="block text-sm font-semibold"
                :class="sale.profit_eur >= 0 ? 'text-(--app-green)' : 'text-(--app-red)'"
              >
                {{ formatSignedPrice(sale.profit_eur) }}
              </span>
              <span v-if="sale.purchase_price_eur > 0" class="text-muted block text-xs">
                {{ formatReturnOnPurchase(sale.profit_eur, sale.purchase_price_eur) }}
              </span>
            </template>
          </GoupixDexDashboardArticleRow>
        </div>
        <p v-else class="text-muted py-6 text-center text-sm">Aucune vente sur cette période.</p>
      </UCard>

      <UCard :ui="{ body: 'p-4' }">
        <div class="mb-3 flex items-center justify-between gap-2">
          <h2 class="text-highlighted text-sm font-semibold">Ventes les plus rapides</h2>
          <span class="text-muted shrink-0 text-xs">de l'ajout à la vente</span>
        </div>
        <div v-if="props.stats.fastest_sold.length" class="divide-y divide-[var(--app-line-soft)]">
          <GoupixDexDashboardArticleRow
            v-for="sale in props.stats.fastest_sold"
            :key="sale.article_id"
            :article-id="sale.article_id"
            :title="sale.title"
            :pokemon-name="sale.pokemon_name"
            :image-url="sale.image_url"
          >
            <template #subtitle>
              <GoupixDexMarketplaceAppIcon v-if="sale.sale_source" :marketplace="sale.sale_source" is-small />
              <span class="truncate">vendu {{ formatPrice(sale.realized_price_eur) }}</span>
            </template>
            <template #trailing>
              <span class="text-highlighted block text-sm font-semibold">
                {{ sale.hours_to_sell === null ? '—' : formatDurationHours(sale.hours_to_sell) }}
              </span>
              <span class="text-muted block text-xs">{{ formatSaleDate(sale.sold_at) }}</span>
            </template>
          </GoupixDexDashboardArticleRow>
        </div>
        <p v-else class="text-muted py-6 text-center text-sm">Aucune vente sur cette période.</p>
      </UCard>

      <UCard :ui="{ body: 'p-4' }">
        <div class="mb-3 flex items-center justify-between gap-2">
          <h2 class="text-highlighted text-sm font-semibold">Stock en vente</h2>
          <span class="text-muted inline-flex shrink-0 items-center gap-1 text-xs">
            <UIcon name="i-lucide-clock" class="size-3" />
            <span class="sm:hidden">Aujourd'hui</span>
            <span class="max-sm:hidden">Aujourd'hui, quelle que soit la période</span>
          </span>
        </div>
        <dl class="grid grid-cols-2 gap-2.5">
          <div class="rounded-lg bg-(--app-bg) px-3 py-2.5">
            <dt class="app-label truncate">Articles</dt>
            <dd class="text-highlighted mt-1 text-lg font-semibold tabular-nums">
              {{ numberFormatter.format(props.stats.inventory_count) }}
            </dd>
          </div>
          <div class="rounded-lg bg-(--app-bg) px-3 py-2.5">
            <dt class="app-label truncate">Prix affichés</dt>
            <dd class="text-highlighted mt-1 text-lg font-semibold tabular-nums">
              {{ formatPrice(props.stats.inventory_sell_total_eur) }}
            </dd>
          </div>
          <div class="rounded-lg bg-(--app-bg) px-3 py-2.5">
            <dt class="app-label truncate">Coût d'achat</dt>
            <dd class="text-highlighted mt-1 text-lg font-semibold tabular-nums">
              {{ formatPrice(props.stats.inventory_purchase_total_eur) }}
            </dd>
          </div>
          <div class="rounded-lg bg-(--app-bg) px-3 py-2.5">
            <dt class="app-label truncate">
              <span class="sm:hidden">Bénéf. potentiel</span>
              <span class="max-sm:hidden">Bénéfice potentiel</span>
            </dt>
            <dd
              class="mt-1 text-lg font-semibold tabular-nums"
              :class="props.stats.inventory_estimated_profit_eur >= 0 ? 'text-(--app-green)' : 'text-(--app-red)'"
            >
              {{ formatSignedPrice(props.stats.inventory_estimated_profit_eur) }}
            </dd>
          </div>
        </dl>
        <template v-if="props.stats.inventory_longest_listed.length">
          <p class="app-label mt-4 mb-2.5">En vente depuis le plus longtemps</p>
          <div class="divide-y divide-[var(--app-line-soft)]">
            <GoupixDexDashboardArticleRow
              v-for="article in props.stats.inventory_longest_listed"
              :key="article.article_id"
              :article-id="article.article_id"
              :title="article.title"
              :pokemon-name="article.pokemon_name"
              :image-url="article.image_url"
            >
              <template #subtitle>
                <span class="truncate">{{ buildListedSinceLabel(article.created_at) }}</span>
              </template>
              <template #trailing>
                <span class="text-highlighted text-sm font-semibold">{{ formatPrice(article.sell_price_eur) }}</span>
              </template>
            </GoupixDexDashboardArticleRow>
          </div>
        </template>
        <NuxtLink
          to="/articles"
          class="text-muted hover:text-highlighted mt-3.5 inline-flex items-center gap-1 text-xs font-medium transition-colors"
        >
          Voir le stock <UIcon name="i-lucide-arrow-right" class="size-3" />
        </NuxtLink>
      </UCard>
    </div>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType } from 'vue'
import type { DashboardPreviousPeriod, DashboardStats, SaleRow } from '~/composables/useStats'
import type { GoupixDexSalesDashboardProps } from '~/types/GoupixDexSalesDashboard'
import type { DashboardRangePresetId } from '~/utils/dashboardRange'
import { formatDurationHours } from '~/utils/relativeTime'

const props: GoupixDexSalesDashboardProps = defineProps({
  stats: {
    type: Object as PropType<DashboardStats>,
    required: true,
  },
  rangePresetId: {
    type: String as PropType<DashboardRangePresetId | null>,
    default: null,
  },
})

const PREVIOUS_PERIOD_LABELS: Record<DashboardRangePresetId, string> = {
  days7: '7 j précédents',
  days30: '30 j précédents',
  months3: '3 mois précédents',
  months12: '12 mois précédents',
  all: 'la période précédente',
}

const DAY_IN_MILLISECONDS: number = 86_400_000

const roundedEuroFormatter: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
})

const priceFormatter: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  trailingZeroDisplay: 'stripIfInteger',
})

const numberFormatter: Intl.NumberFormat = new Intl.NumberFormat('fr-FR')

const dayMonthFormatter: Intl.DateTimeFormat = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short' })

const fullDateFormatter: Intl.DateTimeFormat = new Intl.DateTimeFormat('fr-FR', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})

const previousPeriodLabel: ComputedRef<string> = computed((): string =>
  props.rangePresetId ? PREVIOUS_PERIOD_LABELS[props.rangePresetId] : 'la période précédente',
)

const revenueTrendPercent: ComputedRef<number | null> = computed((): number | null =>
  computePercentChange(props.stats.revenue_period_eur, props.stats.previous_period?.revenue_eur),
)

const profitTrendPercent: ComputedRef<number | null> = computed((): number | null =>
  computePercentChange(props.stats.profit_period_eur, props.stats.previous_period?.profit_eur),
)

const salesCountTrendPercent: ComputedRef<number | null> = computed((): number | null =>
  computePercentChange(props.stats.period_sales_count, props.stats.previous_period?.sales_count),
)

const revenueDescription: ComputedRef<string> = computed((): string => {
  const previousPeriod: DashboardPreviousPeriod | null = props.stats.previous_period

  if (!previousPeriod) {
    return `depuis le ${fullDateFormatter.format(new Date(props.stats.range.start))}`
  }
  return previousPeriod.sales_count > 0 ? `vs ${previousPeriodLabel.value}` : 'aucune vente sur la période précédente'
})

const profitDescription: ComputedRef<string | undefined> = computed((): string | undefined => {
  if (props.stats.revenue_period_eur <= 0) {
    return undefined
  }

  const marginPercent: number = Math.round((props.stats.profit_period_eur / props.stats.revenue_period_eur) * 100)
  return `marge ${marginPercent} %`
})

const salesCountDescription: ComputedRef<string | undefined> = computed((): string | undefined => {
  if (props.stats.period_sales_count === 0) {
    return undefined
  }

  const averageSale: number = props.stats.revenue_period_eur / props.stats.period_sales_count
  return `panier moyen ${roundedEuroFormatter.format(averageSale)}`
})

const topProfitableShareLabel: ComputedRef<string> = computed((): string => {
  const isWholePeriodListed: boolean = props.stats.period_sales_count <= props.stats.top_profitable.length

  if (isWholePeriodListed || props.stats.profit_period_eur <= 0) {
    return ''
  }

  const listedProfit: number = props.stats.top_profitable.reduce(
    (total: number, sale: SaleRow): number => total + sale.profit_eur,
    0,
  )
  return `${Math.round((listedProfit / props.stats.profit_period_eur) * 100)} % du bénéfice`
})

/**
 * Évolution en % d'un chiffre de la période par rapport à la période précédente.
 * @param {number} current - Valeur sur la période.
 * @param {number | undefined} previous - Valeur sur la période précédente, absente sans comparaison possible.
 * @returns {number | null} Le pourcentage arrondi, ou null sans base de comparaison positive.
 */
function computePercentChange(current: number, previous: number | undefined): number | null {
  if (previous === undefined || previous <= 0) {
    return null
  }
  return Math.round(((current - previous) / previous) * 100)
}

/**
 * Prix au centime près, sans « ,00 » pour un montant rond.
 * @param {number | null} amount - Montant en euros.
 * @returns {string} « 89 € », « 4,50 € » ou « — » sans montant.
 */
function formatPrice(amount: number | null): string {
  return amount === null ? '—' : priceFormatter.format(amount)
}

/**
 * Marge signée d'une vente.
 * @param {number} amount - Marge en euros.
 * @returns {string} « +41 € », « -3 € ».
 */
function formatSignedPrice(amount: number): string {
  return `${amount > 0 ? '+' : ''}${priceFormatter.format(amount)}`
}

/**
 * Rendement d'une vente par rapport à son prix d'achat.
 * @param {number} profit - Marge de la vente.
 * @param {number} purchasePrice - Prix d'achat, strictement positif.
 * @returns {string} « +517 % ».
 */
function formatReturnOnPurchase(profit: number, purchasePrice: number): string {
  const returnPercent: number = Math.round((profit / purchasePrice) * 100)
  return `${returnPercent > 0 ? '+' : ''}${numberFormatter.format(returnPercent)} %`
}

/**
 * Date d'une vente, avec l'année seulement si ce n'est pas l'année en cours.
 * @param {string | null} soldAt - Date ISO de la vente.
 * @returns {string} « 28 oct. », « 28 oct. 2025 » ou « — ».
 */
function formatSaleDate(soldAt: string | null): string {
  if (!soldAt) {
    return '—'
  }

  const soldDate: Date = new Date(soldAt)
  const isThisYear: boolean = soldDate.getFullYear() === new Date().getFullYear()
  return isThisYear ? dayMonthFormatter.format(soldDate) : fullDateFormatter.format(soldDate)
}

/**
 * Ancienneté d'un article du stock, comptée depuis son ajout.
 * @param {string | null} createdAt - Date ISO d'ajout de l'article.
 * @returns {string} « en vente depuis 74 j », « en vente depuis aujourd'hui » ou une chaîne vide.
 */
function buildListedSinceLabel(createdAt: string | null): string {
  if (!createdAt) {
    return ''
  }

  const days: number = Math.floor((Date.now() - new Date(createdAt).getTime()) / DAY_IN_MILLISECONDS)
  return days <= 0 ? "en vente depuis aujourd'hui" : `en vente depuis ${days} j`
}
</script>
