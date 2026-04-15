/**
 * Titre d’onglet + meta description avec marque GoupixDex (Open Graph aligné).
 */
export function useGoupixPageSeo(pageTitle: string, description: string) {
  const branded = `${pageTitle} · GoupixDex`
  useSeoMeta({
    title: branded,
    ogTitle: branded,
    description,
    ogDescription: description
  })
}
