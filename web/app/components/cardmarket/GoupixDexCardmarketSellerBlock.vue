<template>
  <div class="space-y-2">
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <a
        v-if="profileHref"
        :href="profileHref"
        target="_blank"
        rel="noopener noreferrer"
        class="text-primary max-w-[16rem] truncate font-medium underline-offset-2 hover:underline"
      >
        {{ sellerName }}
      </a>
      <span v-else class="text-highlighted font-medium">{{ sellerName }}</span>
      <span class="text-muted text-xs tabular-nums">{{ covered }} cartes · {{ totalStr }}</span>
    </div>
    <p v-if="overStr" class="text-warning text-xs">{{ overStr }}</p>
    <ul class="list-disc space-y-0.5 pl-4">
      <li v-for="line in offerLines" :key="line.code" class="text-muted text-xs">{{ line.text }}</li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { cardmarketSellerProfileUrl } from '~/utils/cardmarket'

const props = defineProps<{
  row: Record<string, unknown>
}>()

const eurFmt = new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' })

function formatPrice(n: unknown): string {
  const x = typeof n === 'number' ? n : Number(n)
  if (!Number.isFinite(x)) {
    return '—'
  }
  return eurFmt.format(x)
}

const sellerName = computed(() => String(props.row.seller_name || ''))
const profileHref = computed(() => cardmarketSellerProfileUrl(sellerName.value))
const covered = computed(() => Number(props.row.covered_cards ?? 0))
const totalStr = computed(() => formatPrice(props.row.total_price_eur))

const overStr = computed(() => {
  const overPct = props.row.overpay_vs_min_total_percent
  if (typeof overPct === 'number' && Number.isFinite(overPct)) {
    return `+${overPct.toFixed(2)} % vs min (total)`
  }
  return null
})

const offerLines = computed(() => {
  const offers = (props.row.offers_by_code || {}) as Record<string, Record<string, unknown>>
  return Object.keys(offers)
    .sort()
    .map((code) => {
      const o = offers[code] || {}
      const price = formatPrice(o.price_eur)
      let tag = ''
      if (o.is_best_price === true) {
        tag = ' (meilleur prix)'
      } else if (typeof o.delta_vs_min_percent === 'number') {
        tag = ` (+${Number(o.delta_vs_min_percent).toFixed(2)} %)`
      }
      return { code, text: `${code}: ${price}${tag}` }
    })
})
</script>
