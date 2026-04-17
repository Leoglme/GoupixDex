<script setup lang="ts">
import type { Article } from '~/composables/useArticles'
import type { PricingLookup } from '~/composables/usePricing'

defineProps<{
  article: Article
  pricing?: PricingLookup | null
}>()

const config = useRuntimeConfig()

function img(url: string) {
  if (url.startsWith('http')) {
    return url
  }
  return `${config.public.apiBase}${url}`
}

const eur = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 2
})
</script>

<template>
  <UCard :ui="{ body: 'p-4 sm:p-5' }">
    <div class="flex gap-3">
      <div
        v-if="article.images?.length"
        class="w-20 shrink-0 rounded-lg overflow-hidden bg-elevated ring ring-default"
      >
        <img
          :src="img(article.images[0]!.image_url)"
          :alt="article.title"
          class="w-full h-24 object-cover"
        >
      </div>
      <div class="min-w-0 flex-1 space-y-1">
        <p class="font-medium text-highlighted truncate">
          {{ article.pokemon_name || article.title }}
        </p>
        <p class="text-xs text-muted truncate">
          {{ article.set_code }} · {{ article.card_number }}
        </p>
        <div class="flex flex-wrap gap-2 text-xs">
          <UBadge
            :color="article.is_sold ? 'success' : 'error'"
            variant="subtle"
          >
            {{ article.is_sold ? 'Vendu' : 'En stock' }}
          </UBadge>
          <UBadge
            :color="(article.published_on_vinted ?? false) ? 'success' : 'neutral'"
            variant="subtle"
          >
            Vinted {{ (article.published_on_vinted ?? false) ? 'oui' : 'non' }}
          </UBadge>
          <UBadge
            :color="(article.published_on_ebay ?? false) ? 'success' : 'neutral'"
            variant="subtle"
          >
            eBay {{ (article.published_on_ebay ?? false) ? 'oui' : 'non' }}
          </UBadge>
          <span class="text-muted">Achat {{ eur.format(article.purchase_price) }}</span>
          <span class="text-muted">
            Vente {{ article.sell_price != null ? eur.format(article.sell_price) : '—' }}
          </span>
          <span
            v-if="pricing?.cardmarket_eur != null"
            class="text-muted"
          >CM {{ eur.format(pricing.cardmarket_eur) }}</span>
        </div>
      </div>
    </div>
  </UCard>
</template>
