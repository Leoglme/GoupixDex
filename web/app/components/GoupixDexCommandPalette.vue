<template>
  <Teleport to="body">
    <Transition name="palette-fade">
      <div
        v-if="isOpen"
        class="fixed inset-0 z-[70] flex items-start justify-center bg-(--app-overlay) px-4 pt-[14vh] backdrop-blur-sm"
        @click.self="close()"
      >
        <div class="app-card w-full max-w-xl overflow-hidden p-0 shadow-(--app-shadow-soft)">
          <div class="flex items-center gap-3 border-b border-(--app-line) px-4 py-3">
            <UIcon name="i-lucide-search" class="h-4 w-4 shrink-0 text-(--app-faint)" />
            <input
              ref="searchInput"
              v-model="query"
              type="text"
              placeholder="Rechercher une page, un article, une carte…"
              class="w-full border-0 bg-transparent text-sm text-(--app-ink) placeholder-(--app-faint) focus:ring-0 focus:outline-none"
              @keydown="handleInputKeydown"
            />
            <span
              class="shrink-0 rounded border border-(--app-line) bg-(--app-bg) px-1.5 py-0.5 font-mono text-[9px] text-(--app-ink-soft) uppercase"
            >
              Échap
            </span>
          </div>

          <div ref="resultsContainer" class="max-h-[50vh] overflow-y-auto p-1.5">
            <template v-for="group in visibleGroups" :key="group.key">
              <p class="app-label px-2.5 pt-2.5 pb-1 !text-[0.6rem]">{{ group.heading }}</p>
              <button
                v-for="item in group.items"
                :key="item.id"
                type="button"
                :data-palette-index="item.flatIndex"
                :class="[
                  'flex w-full cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm transition-colors',
                  item.flatIndex === activeIndex
                    ? 'bg-(--app-surface-2) text-(--app-ink)'
                    : 'text-(--app-ink-soft) hover:bg-(--app-surface-2) hover:text-(--app-ink)',
                ]"
                @click="runItem(item)"
                @mousemove="activeIndex = item.flatIndex"
              >
                <UIcon :name="item.icon" class="h-4 w-4 shrink-0 text-(--app-ink-soft)" />
                <span class="min-w-0 flex-1 truncate font-medium">{{ item.label }}</span>
                <span v-if="item.meta" class="text-muted shrink-0 truncate text-xs">{{ item.meta }}</span>
              </button>
            </template>

            <p v-if="totalResults === 0" class="text-muted px-2.5 py-6 text-center text-sm">
              Aucun résultat pour « {{ query }} ».
            </p>
          </div>

          <div class="text-muted flex items-center gap-3 border-t border-(--app-line) px-4 py-2 text-[10px]">
            <span>↑↓ naviguer</span>
            <span>Entrée ouvrir</span>
            <span class="font-display ml-auto flex items-center gap-1.5">
              <UIcon name="i-lucide-flame" class="h-3 w-3 text-(--app-accent)" />
              GoupixDex
            </span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script lang="ts" setup>
import type { ComputedRef, Ref } from 'vue'
import type { Article } from '~/composables/useArticles'
import type { CollectionCard } from '~/composables/useCollection'
import type { GoupixDexCommandPaletteAction, GoupixDexCommandPaletteGroup } from '~/types/GoupixDexCommandPalette'

const { isOpen, close } = useCommandPalette()
const { isDesktopApp } = useDesktopRuntime()
const { me } = useAuth()
const { listArticles } = useArticles()
const { listCollection } = useCollection()
const colorMode = useColorMode()

const query: Ref<string> = ref('')
const activeIndex: Ref<number> = ref(0)
const searchInput: Ref<HTMLInputElement | null> = ref(null)
const resultsContainer: Ref<HTMLDivElement | null> = ref(null)

/** Cached data sources (loaded on first open). */
const articles: Ref<Article[]> = ref([])
const collectionCards: Ref<CollectionCard[]> = ref([])
const hasLoadedSources: Ref<boolean> = ref(false)

/**
 * Normalize a string for accent-insensitive matching.
 * @param value - Raw string.
 * @returns Lowercased string without diacritics.
 */
function normalize(value: string): string {
  return value.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
}

/**
 * Whether an item matches the current query.
 * @param label - Item label.
 * @param keywords - Extra searchable text.
 * @returns True when every query word is found.
 */
function matches(label: string, keywords: string = ''): boolean {
  const haystack: string = normalize(`${label} ${keywords}`)
  return normalize(query.value)
    .split(/\s+/)
    .filter(Boolean)
    .every((word: string): boolean => haystack.includes(word))
}

/** Groups currently displayed (filtered by the query, flat-indexed). */
const visibleGroups: ComputedRef<GoupixDexCommandPaletteGroup[]> = computed((): GoupixDexCommandPaletteGroup[] => {
  const groups: GoupixDexCommandPaletteGroup[] = []
  let flatIndex: number = 0

  /**
   * Append a group when it has matching items.
   * @param key - Stable group key.
   * @param heading - Visible group heading.
   * @param items - Candidate items (without flat index).
   */
  function pushGroup(
    key: string,
    heading: string,
    items: Array<Omit<GoupixDexCommandPaletteAction, 'flatIndex'>>,
  ): void {
    const kept: GoupixDexCommandPaletteAction[] = items
      .filter((item): boolean => !query.value || matches(item.label, item.keywords))
      .map((item): GoupixDexCommandPaletteAction => ({ ...item, flatIndex: flatIndex++ }))
    if (kept.length) {
      groups.push({ key, heading, items: kept })
    }
  }

  const actions: Array<Omit<GoupixDexCommandPaletteAction, 'flatIndex'>> = [
    {
      id: 'action-create-article',
      label: 'Nouvel article',
      icon: 'i-lucide-plus',
      keywords: 'créer vendre fiche scan',
      run: (): void => {
        navigateTo('/articles/create')
      },
    },
    {
      id: 'action-batch-create',
      label: 'Création groupée',
      icon: 'i-lucide-layers',
      keywords: 'plusieurs articles lot batch',
      run: (): void => {
        navigateTo('/articles/batch-create')
      },
    },
    {
      id: 'action-add-collection',
      label: 'Ajouter à ma collection',
      icon: 'i-lucide-library',
      keywords: 'catalogue carte binder',
      run: (): void => {
        navigateTo('/collection/add')
      },
    },
    {
      id: 'action-import-orders',
      label: 'Importer des factures Cardmarket',
      icon: 'i-lucide-file-up',
      keywords: 'pdf commandes achats',
      run: (): void => {
        navigateTo('/orders')
      },
    },
    {
      id: 'action-toggle-theme',
      label: 'Basculer le thème clair / sombre',
      icon: 'i-lucide-sun-moon',
      keywords: 'dark light mode apparence',
      run: (): void => {
        colorMode.preference = colorMode.value === 'dark' ? 'light' : 'dark'
      },
    },
  ]
  actions.splice(3, 0, {
    id: 'action-scan',
    label: 'Scanner mes cartes',
    icon: 'i-lucide-scan-line',
    keywords: 'caméra photo téléphone caisse entrée sortie',
    run: (): void => {
      navigateTo('/collection/scan')
    },
  })
  pushGroup('actions', 'Actions', actions)

  const pages: Array<{ label: string; icon: string; to: string }> = [
    { label: 'Tableau de bord', icon: 'i-lucide-layout-dashboard', to: '/dashboard' },
    { label: 'Mes articles — Stock', icon: 'i-lucide-package', to: '/articles/stock' },
    { label: 'Mes articles — En ligne', icon: 'i-lucide-store', to: '/articles' },
    { label: 'Mes articles — Vendus', icon: 'i-lucide-badge-check', to: '/articles/sold' },
    { label: 'Marché eBay — Annonces en cours', icon: 'i-lucide-tag', to: '/market' },
    { label: 'Marché eBay — Ventes terminées', icon: 'i-lucide-history', to: '/top-ventes-ebay' },
    { label: "Étiquettes d'envoi", icon: 'i-lucide-mailbox', to: '/shipping-labels' },
    { label: 'Ma collection', icon: 'i-lucide-album', to: '/collection' },
    { label: 'Scanner mes cartes', icon: 'i-lucide-scan-line', to: '/collection/scan' },
    { label: 'Commandes Cardmarket', icon: 'i-lucide-file-text', to: '/orders' },
    { label: 'Paramètres', icon: 'i-lucide-settings', to: '/settings' },
  ]
  // Basket optimization left the sidebar; the palette keeps it findable.
  pages.push({ label: 'Paniers Cardmarket', icon: 'i-lucide-shopping-basket', to: '/panier-cardmarket' })
  if (isDesktopApp.value) {
    pages.push({ label: 'Invitations Amazon', icon: 'i-simple-icons-amazon', to: '/amazon-invites' })
  }
  if (me.value?.is_admin) {
    pages.push({ label: 'Utilisateurs', icon: 'i-lucide-users', to: '/users' })
  }
  pushGroup(
    'pages',
    'Pages',
    pages.map((page): Omit<GoupixDexCommandPaletteAction, 'flatIndex'> => {
      return {
        id: `page-${page.to}`,
        label: page.label,
        icon: page.icon,
        run: (): void => {
          navigateTo(page.to)
        },
      }
    }),
  )

  if (query.value) {
    pushGroup(
      'articles',
      'Articles',
      articles.value.slice(0, 400).map((article: Article): Omit<GoupixDexCommandPaletteAction, 'flatIndex'> => {
        return {
          id: `article-${article.id}`,
          label: article.title,
          icon: article.is_sold ? 'i-lucide-badge-check' : 'i-lucide-package',
          meta: article.is_sold ? 'Vendu' : article.sell_price != null ? `${article.sell_price} €` : undefined,
          keywords: `${article.pokemon_name ?? ''} ${article.set_code ?? ''} ${article.card_number ?? ''}`,
          run: (): void => {
            navigateTo(`/articles/${article.id}`)
          },
        }
      }),
    )

    pushGroup(
      'collection',
      'Ma collection',
      collectionCards.value
        .slice(0, 400)
        .map((card: CollectionCard): Omit<GoupixDexCommandPaletteAction, 'flatIndex'> => {
          return {
            id: `collection-${card.id}`,
            label: card.display_name,
            icon: 'i-lucide-album',
            meta: `${card.set_code ?? card.tcgdex_set_id} · #${card.card_number}`,
            keywords: `${card.set_name ?? ''} ${card.card_name_en ?? ''} ${card.card_name_fr ?? ''}`,
            run: (): void => {
              navigateTo(`/collection/${card.id}`)
            },
          }
        }),
    )
  }

  // Cap dynamic groups so the list stays readable.
  return groups.map((group: GoupixDexCommandPaletteGroup): GoupixDexCommandPaletteGroup => {
    if (group.key === 'articles' || group.key === 'collection') {
      return { ...group, items: group.items.slice(0, 6) }
    }
    return group
  })
})

/** Flat list of displayed items (keyboard navigation target). */
const flatItems: ComputedRef<GoupixDexCommandPaletteAction[]> = computed((): GoupixDexCommandPaletteAction[] => {
  return visibleGroups.value.flatMap((group: GoupixDexCommandPaletteGroup) => group.items)
})

/** Number of displayed results. */
const totalResults: ComputedRef<number> = computed((): number => flatItems.value.length)

/**
 * Execute an item then close the palette.
 * @param item - Selected palette row.
 */
function runItem(item: GoupixDexCommandPaletteAction): void {
  close()
  item.run()
}

/**
 * Load the dynamic sources once (articles + collection), errors ignored.
 * @returns Resolves when both fetches settled.
 */
async function loadSources(): Promise<void> {
  if (hasLoadedSources.value) {
    return
  }
  hasLoadedSources.value = true
  const [articlesResult, collectionResult] = await Promise.all([
    listArticles().catch((): Article[] => []),
    listCollection().then(
      (response): CollectionCard[] => response.items,
      (): CollectionCard[] => [],
    ),
  ])
  articles.value = articlesResult
  collectionCards.value = collectionResult
}

/**
 * Keyboard navigation inside the search input.
 * @param event - Keyboard event.
 */
function handleInputKeydown(event: KeyboardEvent): void {
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    activeIndex.value = Math.min(activeIndex.value + 1, totalResults.value - 1)
    scrollActiveIntoView()
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    activeIndex.value = Math.max(activeIndex.value - 1, 0)
    scrollActiveIntoView()
  } else if (event.key === 'Enter') {
    event.preventDefault()
    const item: GoupixDexCommandPaletteAction | undefined = flatItems.value[activeIndex.value]
    if (item) {
      runItem(item)
    }
  }
}

/**
 * Keep the active row visible while navigating with the arrows.
 */
function scrollActiveIntoView(): void {
  nextTick((): void => {
    const row: HTMLElement | null | undefined = resultsContainer.value?.querySelector(
      `[data-palette-index="${activeIndex.value}"]`,
    )
    row?.scrollIntoView({ block: 'nearest' })
  })
}

/**
 * Global shortcuts: Ctrl/Cmd+K toggles, Escape closes.
 * @param event - Keyboard event.
 */
function handleGlobalKeydown(event: KeyboardEvent): void {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    isOpen.value = !isOpen.value
    return
  }
  if (event.key === 'Escape' && isOpen.value) {
    event.preventDefault()
    close()
  }
}

watch(isOpen, (open: boolean): void => {
  if (open) {
    query.value = ''
    activeIndex.value = 0
    loadSources()
    nextTick((): void => {
      searchInput.value?.focus()
    })
  }
})

watch(query, (): void => {
  activeIndex.value = 0
})

onMounted((): void => {
  window.addEventListener('keydown', handleGlobalKeydown, { capture: true })
})

onBeforeUnmount((): void => {
  window.removeEventListener('keydown', handleGlobalKeydown, { capture: true })
})
</script>
