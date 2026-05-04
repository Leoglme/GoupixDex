<template>
  <article
    class="group border-default bg-elevated/30 hover:bg-elevated/60 hover:border-primary/40 relative flex flex-col overflow-hidden rounded-xl border transition-colors"
  >
    <div class="bg-muted/30 relative aspect-square overflow-hidden">
      <img
        v-if="listing.image_url"
        :src="listing.image_url"
        :alt="listing.title"
        loading="lazy"
        class="size-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
      />
      <div v-else class="text-muted flex size-full items-center justify-center">
        <UIcon name="i-lucide-image-off" class="size-8" />
      </div>
      <span
        v-if="listing.graded"
        class="absolute top-2 left-2 inline-flex items-center gap-1 rounded-full bg-amber-500/90 px-2 py-0.5 text-xs font-semibold text-white shadow-sm"
      >
        <UIcon name="i-lucide-award" class="size-3" />
        {{ listing.graded.grader }}{{ listing.graded.grade ? ` ${listing.graded.grade}` : '' }}
      </span>
      <span
        v-if="countryLabel"
        class="absolute top-2 right-2 inline-flex items-center gap-1 rounded-full bg-black/65 px-2 py-0.5 text-xs font-medium text-white backdrop-blur"
        :class="isFrench ? 'ring-primary/70 ring-1' : ''"
      >
        <UIcon :name="isFrench ? 'i-lucide-map-pin' : 'i-lucide-globe'" class="size-3" />
        {{ countryLabel }}
      </span>
    </div>

    <div class="flex flex-1 flex-col gap-3 p-3">
      <div class="space-y-1">
        <h3 class="text-highlighted line-clamp-2 text-sm leading-snug font-medium">
          {{ listing.title }}
        </h3>
        <div class="flex flex-wrap items-center gap-2">
          <span class="text-primary text-lg font-semibold tabular-nums">
            {{ priceFormatted }}
          </span>
          <span v-if="buyingOptionLabel" class="text-muted text-[11px] font-medium"> · {{ buyingOptionLabel }} </span>
        </div>
      </div>

      <div class="text-muted flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
        <span v-if="listing.condition" class="inline-flex items-center gap-1">
          <UIcon name="i-lucide-tag" class="size-3" />
          {{ listing.condition }}
        </span>
        <span v-if="listing.seller_username" class="inline-flex items-center gap-1">
          <UIcon name="i-lucide-user" class="size-3" />
          {{ listing.seller_username }}
          <span v-if="listing.seller_feedback_score != null" class="text-muted text-[10px]">
            ({{ listing.seller_feedback_score.toLocaleString('fr-FR') }})
          </span>
        </span>
      </div>

      <div class="mt-auto flex flex-wrap gap-2 pt-1">
        <UButton
          :to="listing.listing_url"
          target="_blank"
          rel="noopener"
          size="xs"
          color="neutral"
          variant="subtle"
          icon="i-lucide-external-link"
        >
          Voir sur eBay
        </UButton>
        <UButton size="xs" color="primary" variant="soft" icon="i-lucide-plus" @click="emit('createArticle', listing)">
          Créer article
        </UButton>
      </div>
    </div>
  </article>
</template>

<script setup lang="ts">
import type { MarketListing } from '~/composables/useMarketSearch'

const props = defineProps<{
  listing: MarketListing
}>()

const emit = defineEmits<{
  createArticle: [listing: MarketListing]
}>()

const eur = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const priceFormatted = computed(() => {
  if (props.listing.currency && props.listing.currency !== 'EUR') {
    const fallback = new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: props.listing.currency,
    })
    return fallback.format(props.listing.price_eur)
  }
  return eur.format(props.listing.price_eur)
})

const countryLabel = computed(() => {
  const code = (props.listing.seller_country || '').toUpperCase()
  if (!code) {
    return null
  }
  const names: Record<string, string> = {
    FR: 'France',
    BE: 'Belgique',
    DE: 'Allemagne',
    IT: 'Italie',
    ES: 'Espagne',
    NL: 'Pays-Bas',
    LU: 'Luxembourg',
    PT: 'Portugal',
    GB: 'Royaume-Uni',
    CH: 'Suisse',
  }
  return names[code] ?? code
})

const isFrench = computed(() => (props.listing.seller_country || '').toUpperCase() === 'FR')

const buyingOptionLabel = computed(() => {
  const opts = props.listing.buying_options || []
  if (opts.includes('FIXED_PRICE')) {
    return 'Achat immédiat'
  }
  if (opts.includes('AUCTION')) {
    return 'Enchère'
  }
  if (opts.includes('BEST_OFFER')) {
    return 'Offre possible'
  }
  return null
})
</script>
