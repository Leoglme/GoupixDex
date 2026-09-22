<template>
  <GoupixDexArticleDrawer
    :open="articleEntry !== null"
    :article-id="articleEntry?.articleId ?? null"
    :header-title="articleHeaderTitle"
    :header-subtitle="articleHeaderSubtitle"
    :show-back="hasPrevious"
    :browse-position-label="articleBrowsePositionLabel"
    :can-browse-previous="canBrowsePreviousArticle"
    :can-browse-next="canBrowseNextArticle"
    @close="drawerStack.closeAll()"
    @back="drawerStack.back()"
    @browse-previous="browseArticle(-1)"
    @browse-next="browseArticle(1)"
    @updated="onArticleUpdated"
  />

  <GoupixDexSealedProductDrawer
    :open="sealedEntry !== null"
    :sealed-id="sealedEntry?.sealedId ?? null"
    :header-title="sealedHeaderTitle"
    :header-subtitle="sealedHeaderSubtitle"
    :show-back="hasPrevious"
    @close="drawerStack.closeAll()"
    @back="drawerStack.back()"
    @updated="onSealedUpdated"
    @deleted="onSealedDeleted"
  />

  <GoupixDexCollectionCardDrawer
    :open="cardEntry !== null"
    :card-id="cardEntry?.cardId ?? null"
    :header-title="cardHeaderTitle"
    :header-subtitle="cardHeaderSubtitle"
    :show-back="hasPrevious"
    @close="drawerStack.closeAll()"
    @back="drawerStack.back()"
    @updated="onCardUpdated"
    @deleted="onCardDeleted"
  />

  <GoupixDexSealedCatalogPreviewDrawer
    :open="catalogEntry !== null"
    :product="catalogEntry?.product ?? null"
    :expansion-name="catalogEntry?.expansionName ?? ''"
    :show-back="hasPrevious"
    @close="drawerStack.closeAll()"
    @back="drawerStack.back()"
    @added="onCatalogAdded"
  />

  <GoupixDexCardCatalogPreviewDrawer
    :open="catalogCardEntry !== null"
    :card="catalogCardEntry?.card ?? null"
    :show-back="hasPrevious"
    @close="drawerStack.closeAll()"
    @back="drawerStack.back()"
    @added="onCatalogCardAdded"
  />
</template>

<script setup lang="ts">
import type { Article } from '~/composables/useArticles'
import type { CollectionCard } from '~/composables/useCollection'
import type { SealedProduct } from '~/composables/useSealed'
import type {
  GoupixArticleDrawerEntry,
  GoupixCardDrawerEntry,
  GoupixCatalogCardDrawerEntry,
  GoupixSealedCatalogDrawerEntry,
  GoupixSealedDrawerEntry,
} from '~/types/GoupixDrawerStack'

const drawerStack = useGoupixDrawerStack()
const { getArticle } = useArticles()
const { getSealed } = useSealed()
const { getCollectionCard } = useCollection()

const topEntry = computed(() => drawerStack.topEntry.value)
const hasPrevious = computed(() => drawerStack.hasPrevious.value)

const articleEntry = computed((): GoupixArticleDrawerEntry | null => {
  const top = topEntry.value
  return top?.kind === 'article' ? top : null
})

const articleHeaderCache = ref<Map<number, { title: string; subtitle: string }>>(new Map())

const articleHeaderTitle = computed((): string => {
  const id = articleEntry.value?.articleId
  if (!id) {
    return 'Article'
  }
  return articleHeaderCache.value.get(id)?.title ?? 'Article'
})

const articleHeaderSubtitle = computed((): string => {
  const id = articleEntry.value?.articleId
  if (!id) {
    return ''
  }
  return articleHeaderCache.value.get(id)?.subtitle ?? ''
})

const browseIndex = computed((): number => {
  const id = articleEntry.value?.articleId
  if (id == null) {
    return -1
  }
  return drawerStack.articleBrowseIds.value.indexOf(id)
})

const articleBrowsePositionLabel = computed((): string => {
  const ids = drawerStack.articleBrowseIds.value
  if (browseIndex.value < 0 || !ids.length) {
    return ''
  }
  return `${browseIndex.value + 1} / ${ids.length}`
})

const canBrowsePreviousArticle = computed((): boolean => browseIndex.value > 0)

const canBrowseNextArticle = computed(
  (): boolean => browseIndex.value >= 0 && browseIndex.value < drawerStack.articleBrowseIds.value.length - 1,
)

function browseArticle(step: -1 | 1): void {
  const idx = browseIndex.value
  if (idx < 0) {
    return
  }
  const targetId = drawerStack.articleBrowseIds.value[idx + step]
  if (targetId != null) {
    drawerStack.pushArticle(targetId)
  }
}

function onArticleUpdated(article: Article): void {
  articleHeaderCache.value.set(article.id, {
    title: article.pokemon_name || article.title || 'Article',
    subtitle: article.title || '',
  })
  drawerStack.notifyArticleUpdated(article.id)
}

watch(
  () => articleEntry.value?.articleId,
  (id) => {
    if (id == null) {
      return
    }
    if (articleHeaderCache.value.has(id)) {
      return
    }
    void getArticle(id)
      .then((row) => {
        articleHeaderCache.value.set(id, {
          title: row.pokemon_name || row.title || 'Article',
          subtitle: row.title || '',
        })
      })
      .catch(() => {})
  },
  { immediate: true },
)

const sealedEntry = computed((): GoupixSealedDrawerEntry | null => {
  const top = topEntry.value
  return top?.kind === 'sealed' ? top : null
})

const sealedHeaderCache = ref<Map<number, { title: string; subtitle: string }>>(new Map())

const sealedHeaderTitle = computed((): string => {
  const id = sealedEntry.value?.sealedId
  if (!id) {
    return 'Produit scellé'
  }
  return sealedHeaderCache.value.get(id)?.title ?? 'Produit scellé'
})

const sealedHeaderSubtitle = computed((): string => {
  const id = sealedEntry.value?.sealedId
  if (!id) {
    return ''
  }
  return sealedHeaderCache.value.get(id)?.subtitle ?? ''
})

function onSealedUpdated(product: SealedProduct): void {
  sealedHeaderCache.value.set(product.id, {
    title: product.name || 'Produit scellé',
    subtitle: product.set_name || '',
  })
  drawerStack.notifySealedUpdated(product.id)
}

function onSealedDeleted(sealedId: number): void {
  drawerStack.notifySealedDeleted(sealedId)
  drawerStack.back()
}

watch(
  () => sealedEntry.value?.sealedId,
  (id) => {
    if (id == null || sealedHeaderCache.value.has(id)) {
      return
    }
    void getSealed(id)
      .then((row) => {
        sealedHeaderCache.value.set(id, { title: row.name || 'Produit scellé', subtitle: row.set_name || '' })
      })
      .catch(() => {})
  },
  { immediate: true },
)

const cardEntry = computed((): GoupixCardDrawerEntry | null => {
  const top = topEntry.value
  return top?.kind === 'card' ? top : null
})

const cardHeaderCache = ref<Map<number, { title: string; subtitle: string }>>(new Map())

const cardHeaderTitle = computed((): string => {
  const id = cardEntry.value?.cardId
  if (!id) {
    return 'Carte de collection'
  }
  return cardHeaderCache.value.get(id)?.title ?? 'Carte de collection'
})

const cardHeaderSubtitle = computed((): string => {
  const id = cardEntry.value?.cardId
  if (!id) {
    return ''
  }
  return cardHeaderCache.value.get(id)?.subtitle ?? ''
})

function onCardUpdated(card: CollectionCard): void {
  cardHeaderCache.value.set(card.id, {
    title: card.display_name || 'Carte de collection',
    subtitle: card.set_name || card.tcgdex_set_id || '',
  })
  drawerStack.notifyCardUpdated(card.id)
}

function onCardDeleted(cardId: number): void {
  drawerStack.notifyCardDeleted(cardId)
  drawerStack.back()
}

watch(
  () => cardEntry.value?.cardId,
  (id) => {
    if (id == null || cardHeaderCache.value.has(id)) {
      return
    }
    void getCollectionCard(id)
      .then((row) => {
        cardHeaderCache.value.set(id, {
          title: row.display_name || 'Carte de collection',
          subtitle: row.set_name || row.tcgdex_set_id || '',
        })
      })
      .catch(() => {})
  },
  { immediate: true },
)

const catalogEntry = computed((): GoupixSealedCatalogDrawerEntry | null => {
  const top = topEntry.value
  return top?.kind === 'catalog-sealed' ? top : null
})

function onCatalogAdded(product: SealedProduct): void {
  drawerStack.notifySealedUpdated(product.id)
}

const catalogCardEntry = computed((): GoupixCatalogCardDrawerEntry | null => {
  const top = topEntry.value
  return top?.kind === 'catalog-card' ? top : null
})

function onCatalogCardAdded(card: CollectionCard): void {
  drawerStack.notifyCardUpdated(card.id)
}

function onEscape(event: KeyboardEvent): void {
  if (event.key === 'Escape' && !event.defaultPrevented && topEntry.value) {
    drawerStack.back()
  }
}

onMounted(() => {
  drawerStack.restoreStackFromSession()
  window.addEventListener('keydown', onEscape)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onEscape)
})

watch(topEntry, (entry) => {
  if (!import.meta.client) {
    return
  }
  document.body.style.overflow = entry ? 'hidden' : ''
})
</script>
