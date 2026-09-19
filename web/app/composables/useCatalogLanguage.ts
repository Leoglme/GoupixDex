import type { CatalogLocale } from '~/composables/useCardCatalog'

const STORAGE_KEY = 'goupix_catalog_language'

export type CatalogLanguage = CatalogLocale

/**
 * Langue catalogue TCGdex et langue physique des cartes ajoutées (une seule préférence).
 */
export function useCatalogLanguage() {
  const catalogLanguage = useState<CatalogLanguage>('goupix-catalog-language', () => 'fr')

  if (import.meta.client) {
    onMounted(() => {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (raw === 'fr' || raw === 'en' || raw === 'ja') {
        catalogLanguage.value = raw
      }
    })

    watch(catalogLanguage, (v) => {
      localStorage.setItem(STORAGE_KEY, v)
    })
  }

  const catalogLanguageItems = [
    { label: 'Français', value: 'fr' as const },
    { label: 'English', value: 'en' as const },
    { label: 'Japonais', value: 'ja' as const },
  ]

  return { catalogLanguage, catalogLanguageItems }
}
