<template>
  <UDashboardPanel :id="`article-view-${id}`">
    <template #header>
      <UDashboardNavbar title="Article">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <div class="flex flex-wrap items-center gap-2">
            <UButton :to="`/articles/${id}/edit`" color="primary" icon="i-lucide-pencil"> Modifier </UButton>
            <UButton to="/articles/stock" color="neutral" variant="ghost" icon="i-lucide-package"> Mon stock </UButton>
          </div>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="w-full space-y-6 p-4 sm:p-6">
        <div v-if="loading" class="flex justify-center py-20">
          <UIcon name="i-lucide-loader-2" class="text-primary size-10 animate-spin" />
        </div>

        <template v-else-if="article">
          <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div class="min-w-0 space-y-1">
              <p class="text-primary text-xs font-medium tracking-wide uppercase">Fiche article</p>
              <h1 class="text-highlighted text-2xl font-semibold tracking-tight">
                {{ article.pokemon_name || article.title }}
              </h1>
              <p class="text-muted text-sm">{{ article.title }}</p>
            </div>
            <div class="flex flex-wrap gap-2">
              <UBadge :color="article.is_sold ? 'success' : 'warning'" variant="subtle">
                {{ article.is_sold ? 'Vendu' : 'En stock' }}
              </UBadge>
              <UBadge :color="(article.published_on_vinted ?? false) ? 'success' : 'neutral'" variant="subtle">
                Vinted {{ (article.published_on_vinted ?? false) ? 'oui' : 'non' }}
              </UBadge>
              <UBadge :color="(article.published_on_ebay ?? false) ? 'success' : 'neutral'" variant="subtle">
                eBay {{ (article.published_on_ebay ?? false) ? 'oui' : 'non' }}
              </UBadge>
            </div>
          </div>

          <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <UCard class="ring-default/60 shadow-sm ring-1" :ui="{ body: 'p-4' }">
              <p class="text-muted text-xs font-medium uppercase">Prix d'achat</p>
              <p class="text-highlighted mt-1 text-xl font-semibold tabular-nums">
                {{ eur.format(article.purchase_price) }}
              </p>
            </UCard>
            <UCard class="ring-default/60 shadow-sm ring-1" :ui="{ body: 'p-4' }">
              <p class="text-muted text-xs font-medium uppercase">Prix de vente</p>
              <p class="text-highlighted mt-1 text-xl font-semibold tabular-nums">
                {{ article.sell_price != null ? eur.format(article.sell_price) : '—' }}
              </p>
            </UCard>
            <UCard class="ring-default/60 shadow-sm ring-1" :ui="{ body: 'p-4' }">
              <p class="text-muted text-xs font-medium uppercase">Code set</p>
              <p class="text-highlighted mt-1 text-lg font-semibold">
                {{ article.set_code || '—' }}
              </p>
            </UCard>
            <UCard class="ring-default/60 shadow-sm ring-1" :ui="{ body: 'p-4' }">
              <p class="text-muted text-xs font-medium uppercase">N° carte</p>
              <p class="text-highlighted mt-1 text-lg font-semibold">
                {{ article.card_number || '—' }}
              </p>
            </UCard>
          </div>

          <UCard
            v-if="article.order_context"
            class="border-primary/25 from-primary/10 ring-primary/20 bg-gradient-to-br to-transparent ring-1"
            :ui="{ body: 'p-5 sm:p-6' }"
          >
            <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div class="space-y-1">
                <p class="text-primary text-xs font-medium uppercase">Achat Cardmarket</p>
                <p class="text-highlighted text-lg font-semibold">
                  Commande #{{ article.order_context.external_order_id }}
                </p>
                <p class="text-muted text-sm">
                  Payé le
                  {{
                    article.order_context.paid_at
                      ? new Date(article.order_context.paid_at).toLocaleDateString('fr-FR')
                      : '—'
                  }}
                  · Prix ligne {{ eur.format(article.order_context.unit_price_eur) }}
                </p>
                <p
                  v-if="article.order_context.seller_username"
                  class="text-muted flex flex-wrap items-center gap-x-2 gap-y-1 text-xs"
                >
                  <span>Vendeur :</span>
                  <a
                    v-if="articleSellerProfileUrl"
                    :href="articleSellerProfileUrl"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="text-primary font-medium underline-offset-2 hover:underline"
                  >
                    {{ article.order_context.seller_username }}
                  </a>
                  <span v-else>{{ article.order_context.seller_username }}</span>
                  <img
                    v-if="articleOrderCountryFlagSrc"
                    :src="articleOrderCountryFlagSrc"
                    alt=""
                    width="20"
                    height="15"
                    class="inline-block h-[15px] w-5 shrink-0 rounded-sm object-cover"
                    loading="lazy"
                    decoding="async"
                  />
                  <span v-if="article.order_context.seller_country_code" class="sr-only">{{
                    article.order_context.seller_country_code
                  }}</span>
                </p>
              </div>
              <UButton :to="`/orders/${article.order_context.order_id}`" icon="i-lucide-file-text" color="primary">
                Voir la commande
              </UButton>
            </div>
          </UCard>

          <UCard class="ring-default/60 shadow-sm ring-1" :ui="{ body: 'p-5 sm:p-6 space-y-4' }">
            <p class="text-highlighted font-medium">Description</p>
            <p class="text-muted text-sm leading-relaxed whitespace-pre-wrap">
              {{ article.description }}
            </p>
          </UCard>

          <div v-if="article.images?.length" class="space-y-3">
            <p class="text-highlighted text-sm font-medium">Photos</p>
            <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <div v-for="img in article.images" :key="img.id" class="ring-default overflow-hidden rounded-xl ring-1">
                <img :src="imageSrc(img.image_url)" :alt="article.title" class="block h-auto w-full" />
              </div>
            </div>
          </div>

          <div class="text-muted border-default flex flex-wrap gap-x-6 gap-y-2 border-t pt-4 text-xs">
            <span>Créé le {{ new Date(article.created_at).toLocaleString('fr-FR') }}</span>
            <span v-if="article.sold_at">Vendu le {{ new Date(article.sold_at).toLocaleString('fr-FR') }}</span>
          </div>
        </template>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { ComputedRef, Ref } from 'vue'
import type { Article } from '~/composables/useArticles'
import { cardmarketSellerProfileUrl } from '~/utils/cardmarket'
import { countryFlagImgUrl } from '~/utils/flagEmoji'

definePageMeta({ middleware: 'auth' })

const route = useRoute()
const config = useRuntimeConfig()
const { getArticle } = useArticles()
const toast = useToast()

const article: Ref<Article | null> = ref(null)
const loading: Ref<boolean> = ref(true)

const id: ComputedRef<number> = computed(() => Number(route.params.id))

const eur: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
})

const articleOrderCountryFlagSrc: ComputedRef<string | null> = computed(() =>
  article.value?.order_context?.seller_country_code
    ? countryFlagImgUrl(article.value.order_context.seller_country_code)
    : null,
)

const articleSellerProfileUrl: ComputedRef<string | null> = computed(() =>
  cardmarketSellerProfileUrl(article.value?.order_context?.seller_username ?? null),
)

async function load(): Promise<void> {
  loading.value = true
  try {
    article.value = await getArticle(id.value)
  } catch (e) {
    toast.add({ title: 'Article introuvable', description: apiErrorMessage(e), color: 'error' })
    await navigateTo('/articles')
  } finally {
    loading.value = false
  }
}

/**
 * Resolve image URL for preview (same rules as the article form).
 * @param url - Stored path or absolute URL.
 * @returns Display URL.
 */
function imageSrc(url: string): string {
  if (url.startsWith('http')) {
    return url
  }
  return `${config.public.apiBase}${url}`
}

useSeoMeta({
  title: computed(() =>
    article.value ? `${article.value.title.slice(0, 48)} · Article · GoupixDex` : 'Article · GoupixDex',
  ),
  description: computed(() =>
    article.value
      ? `Détail de « ${article.value.title} » : prix, photos et lien commande Cardmarket éventuel.`
      : 'Fiche article GoupixDex.',
  ),
})

onMounted((): void => {
  void load()
})
</script>
