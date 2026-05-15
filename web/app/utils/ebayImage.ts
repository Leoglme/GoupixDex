/**
 * eBay's image CDN (``i.ebayimg.com``) serves the same picture at multiple
 * sizes by swapping the ``s-lNNN`` suffix in the path:
 *
 *     https://i.ebayimg.com/images/g/<hash>/s-l140.jpg   ← thumbnail (default in search HTML)
 *     https://i.ebayimg.com/images/g/<hash>/s-l500.jpg   ← medium
 *     https://i.ebayimg.com/images/g/<hash>/s-l1600.jpg  ← large
 *
 * The HTML scrape returns the small thumbnail by default — fine for tiny
 * lists, blurry for the big card grid. These helpers rewrite the URL to a
 * larger variant so the components stay sharp on retina displays.
 *
 * Cached sizes commonly available: 64, 96, 140, 180, 225, 300, 400, 500,
 * 640, 800, 1000, 1200, 1600. We clamp to that range to avoid 404s.
 */

const _MIN_WIDTH = 64
const _MAX_WIDTH = 1600
const _SIZE_RX = /\/s-l\d+(\.[a-zA-Z]{2,5})(\?.*)?$/

/**
 * Rewrite an eBay image URL to target a specific pixel width. Non-eBay
 * URLs (or unparseable ones) come back unchanged so this is safe to apply
 * blindly.
 * @param url - The original eBay image URL (or null / undefined).
 * @param targetWidth - Desired pixel width on the long edge.
 * @returns The upgraded URL, or `null` when the input was falsy.
 */
export function upgradeEbayImage(url: string | null | undefined, targetWidth = 500): string | null {
  if (!url) {
    return null
  }
  const safe = Math.min(_MAX_WIDTH, Math.max(_MIN_WIDTH, Math.round(targetWidth)))
  if (!_SIZE_RX.test(url)) {
    return url
  }
  return url.replace(_SIZE_RX, (_match, ext: string, query: string | undefined) => {
    return `/s-l${safe}${ext}${query ?? ''}`
  })
}

/**
 * Build a ``srcset`` string with 1x and 2x variants so the browser picks
 * the right size on retina displays.
 * @param url - The original eBay image URL.
 * @param baseWidth - The 1x target width (the 2x variant is twice as large, clamped).
 * @returns A `srcset` value usable on `<img>`, or `''` if the input was falsy.
 */
export function ebayImageSrcset(url: string | null | undefined, baseWidth = 500): string {
  if (!url) {
    return ''
  }
  const oneX = upgradeEbayImage(url, baseWidth)
  const twoX = upgradeEbayImage(url, baseWidth * 2)
  if (!oneX) {
    return ''
  }
  if (!twoX || twoX === oneX) {
    return `${oneX} 1x`
  }
  return `${oneX} 1x, ${twoX} 2x`
}
