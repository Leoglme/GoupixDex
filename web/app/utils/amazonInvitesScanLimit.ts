/** Approx. invite-only rows per Amazon search page (used to derive page depth). */
export const AMAZON_INVITES_PER_PAGE_EST = 24

export const DEFAULT_AMAZON_INVITES_MAX_ITEMS = 10

export function clampMaxItems(n: number): number {
  if (!Number.isFinite(n)) {
    return DEFAULT_AMAZON_INVITES_MAX_ITEMS
  }
  return Math.min(500, Math.max(1, Math.round(n)))
}

/** Worker scans by page; may scan further server-side until ``max_items`` is filled. */
export function maxItemsToScanPages(maxItems: number, hasAmazonSearchQuery = false): number {
  const items = clampMaxItems(maxItems)
  let pages = Math.ceil(items / AMAZON_INVITES_PER_PAGE_EST)
  if (hasAmazonSearchQuery) {
    pages = Math.max(pages, Math.min(50, Math.max(3, Math.ceil(items / 2))))
  }
  return Math.min(50, Math.max(1, pages))
}

/** Legacy prefs stored page count (1–50). */
export function legacyMaxPagesToMaxItems(maxPages: number): number {
  const pages = Math.min(50, Math.max(1, Math.round(maxPages)))
  return clampMaxItems(pages * AMAZON_INVITES_PER_PAGE_EST)
}
