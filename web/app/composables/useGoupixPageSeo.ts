/**
 * Titre d'onglet + meta description avec marque GoupixDex (Open Graph aligné).
 */
export function useGoupixPageSeo(pageTitle: string, description: string) {
  const runtime = useRuntimeConfig()
  const route = useRoute()
  const siteUrl = (runtime.public.siteUrl as string | undefined)?.trim()
  const canonicalUrl = siteUrl
    ? new URL(route.path || '/', siteUrl).toString()
    : undefined

  if (canonicalUrl) {
    useHead({
      link: [
        { rel: 'canonical', href: canonicalUrl }
      ]
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
    twitterDescription: description
  })
}
