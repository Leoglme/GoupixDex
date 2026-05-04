/**
 * Set tab title, Open Graph, Twitter cards, and canonical URL for the current route.
 *
 * @param pageTitle - Short page title segment (prefixed with `· GoupixDex`).
 * @param description - Meta / OG / Twitter description body.
 * @returns {void} Nothing (`useHead` / `useSeoMeta` side effects only).
 */
export function useGoupixPageSeo(pageTitle: string, description: string): void {
  const runtime = useRuntimeConfig()
  const route = useRoute()
  const siteUrl = (runtime.public.siteUrl as string | undefined)?.trim()
  const canonicalUrl = siteUrl ? new URL(route.path || '/', siteUrl).toString() : undefined

  if (canonicalUrl) {
    useHead({
      link: [{ rel: 'canonical', href: canonicalUrl }],
    })
  }

  const branded = `${pageTitle} · GoupixDex`
  useSeoMeta({
    title: branded,
    ogTitle: branded,
    twitterTitle: branded,
    description,
    ogDescription: description,
    ogSiteName: 'GoupixDex',
    ogUrl: canonicalUrl,
    twitterDescription: description,
  })
}
