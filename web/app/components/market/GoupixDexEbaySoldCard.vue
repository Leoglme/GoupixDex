<template>
  <article
    class="group border-default bg-elevated/30 hover:bg-elevated/60 hover:border-primary/40 relative flex flex-col overflow-hidden rounded-xl border transition-colors"
  >
    <div class="bg-muted/30 relative aspect-square overflow-hidden">
      <img
        v-if="imgSrc"
        :src="imgSrc"
        :srcset="imgSrcset"
        :alt="row.title"
        loading="lazy"
        decoding="async"
        class="size-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
      />
      <div v-else class="text-muted flex size-full items-center justify-center">
        <UIcon name="i-lucide-image-off" class="size-8" />
      </div>
      <span
        class="absolute top-2 left-2 inline-flex items-center gap-1 rounded-full bg-emerald-500/90 px-2 py-0.5 text-xs font-semibold text-white shadow-sm"
      >
        <UIcon name="i-lucide-check-circle-2" class="size-3" />
        Vendu
      </span>
    </div>

    <div class="flex flex-1 flex-col gap-3 p-3">
      <div class="space-y-1">
        <h3 class="text-highlighted line-clamp-2 text-sm leading-snug font-medium">
          {{ row.title }}
        </h3>
        <div class="flex flex-wrap items-center gap-2">
          <span class="text-primary text-lg font-semibold tabular-nums">{{ priceFormatted }}</span>
        </div>
      </div>

      <div v-if="soldLabel" class="text-muted flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
        <span class="inline-flex items-center gap-1" :title="row.sold_caption ?? undefined">
          <UIcon name="i-lucide-calendar-check" class="size-3" />
          {{ soldLabel }}
        </span>
      </div>

      <div class="mt-auto flex flex-wrap gap-2 pt-1">
        <UButton
          :to="row.listing_url"
          target="_blank"
          rel="noopener"
          size="xs"
          color="neutral"
          variant="subtle"
          icon="i-lucide-external-link"
        >
          Voir l'annonce
        </UButton>
      </div>
    </div>
  </article>
</template>

<script setup lang="ts">
import type { EbaySoldScrapeRow } from '~/composables/useEbaySoldScrape'

const props = defineProps<{
  row: EbaySoldScrapeRow
}>()

const eur = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const priceFormatted = computed(() => {
  const v = props.row.price_eur
  if (v == null || !Number.isFinite(v)) {
    return '—'
  }
  return eur.format(v)
})

/**
 * Prefer the parsed relative time (« il y a 2 h ») over the raw eBay
 * caption when available — gives a uniform format across listings, even
 * when eBay returned an absolute date (« 15 mars »).
 */
const soldLabel = computed(() => {
  const rel = formatRelativeHours(props.row.approx_hours_ago)
  if (rel) {
    return rel
  }
  return props.row.sold_caption ?? ''
})

/**
 * Bump the eBay thumbnail (s-l140 by default) to a larger variant so the
 * card image stays sharp at desktop widths and on retina displays.
 */
const imgSrc = computed(() => upgradeEbayImage(props.row.image_url, 500))
const imgSrcset = computed(() => ebayImageSrcset(props.row.image_url, 500))
</script>
