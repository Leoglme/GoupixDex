import type { CatalogLocale, TcgdexSeriesWithSets } from '~/composables/useCardCatalog'

const STORAGE_PREFIX = 'goupix_catalog_browse_v6'
/** Static JSON is immutable until deploy; keep a long client cache. */
const TTL_MS = 7 * 24 * 60 * 60 * 1000

type BrowseCacheEntry = {
  fetchedAt: number
  series: TcgdexSeriesWithSets[]
}

/**
 * Cache client du navigateur d’extensions (mémoire + sessionStorage, 1 h).
 */
export function useCatalogBrowseCache() {
  const memory = useState<Partial<Record<CatalogLocale, BrowseCacheEntry>>>('catalog-browse-cache', () => ({}))

  /**
   *
   */
  function storageKey(locale: CatalogLocale): string {
    return `${STORAGE_PREFIX}:${locale}`
  }

  /**
   *
   */
  function read(locale: CatalogLocale): TcgdexSeriesWithSets[] | null {
    const mem = memory.value[locale]
    if (mem && Date.now() - mem.fetchedAt < TTL_MS) {
      return mem.series
    }
    if (!import.meta.client) {
      return null
    }
    try {
      const raw = sessionStorage.getItem(storageKey(locale))
      if (!raw) {
        return null
      }
      const parsed = JSON.parse(raw) as BrowseCacheEntry
      if (Date.now() - parsed.fetchedAt >= TTL_MS) {
        sessionStorage.removeItem(storageKey(locale))
        return null
      }
      memory.value[locale] = parsed
      return parsed.series
    } catch {
      return null
    }
  }

  /**
   *
   */
  function write(locale: CatalogLocale, series: TcgdexSeriesWithSets[]): void {
    const entry: BrowseCacheEntry = { fetchedAt: Date.now(), series }
    memory.value[locale] = entry
    if (!import.meta.client) {
      return
    }
    try {
      sessionStorage.setItem(storageKey(locale), JSON.stringify(entry))
    } catch {
      /* quota — memory cache still works for the session */
    }
  }

  /**
   *
   */
  function invalidate(locale?: CatalogLocale): void {
    if (locale) {
      const { [locale]: _drop, ...rest } = memory.value
      memory.value = rest
      if (import.meta.client) {
        sessionStorage.removeItem(storageKey(locale))
      }
      return
    }
    memory.value = {}
    if (import.meta.client) {
      for (const loc of ['fr', 'en', 'ja'] as CatalogLocale[]) {
        sessionStorage.removeItem(storageKey(loc))
      }
    }
  }

  return { read, write, invalidate }
}
