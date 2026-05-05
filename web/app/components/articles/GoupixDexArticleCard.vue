<template>
  <UCard :ui="{ body: 'p-4 sm:p-5' }">
    <div class="flex gap-3">
      <div v-if="article.images?.length" class="bg-elevated ring-default w-20 shrink-0 overflow-hidden rounded-lg ring">
        <img :src="img(article.images[0]!.image_url)" :alt="article.title" class="h-24 w-full object-cover" />
      </div>
      <div class="min-w-0 flex-1 space-y-1">
        <p class="text-highlighted truncate font-medium">
          {{ article.pokemon_name || article.title }}
        </p>
        <p class="text-muted truncate text-xs">{{ article.set_code }} · {{ article.card_number }}</p>
        <div class="flex flex-wrap gap-2 text-xs">
          <UBadge :color="article.is_sold ? 'success' : 'error'" variant="subtle">
            {{ article.is_sold ? 'Vendu' : 'En stock' }}
          </UBadge>
          <UBadge :color="(article.published_on_vinted ?? false) ? 'success' : 'neutral'" variant="subtle">
            {{ (article.published_on_vinted ?? false) ? 'Vinted oui' : 'Vinted' }}
          </UBadge>
          <UBadge :color="(article.published_on_ebay ?? false) ? 'success' : 'neutral'" variant="subtle">
            eBay {{ (article.published_on_ebay ?? false) ? 'oui' : 'non' }}
          </UBadge>
          <span class="text-muted">Achat {{ eur.format(article.purchase_price) }}</span>
          <span class="text-muted">
            Vente {{ article.sell_price != null ? eur.format(article.sell_price) : '—' }}
          </span>
        </div>
      </div>
    </div>
  </UCard>
</template>

<script setup lang="ts">
import type { Article } from '~/composables/useArticles'

defineProps<{
  article: Article
}>()

const config = useRuntimeConfig()

/**
 * Resolve API-relative image URL to an absolute URL for `<img src>`.
 * @param url - Stored image path or absolute URL
 * @returns {string} Absolute URL
 */
function img(url: string): string {
  if (url.startsWith('http')) {
    return url
  }
  return `${config.public.apiBase}${url}`
}

const eur = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 2,
})
</script>
