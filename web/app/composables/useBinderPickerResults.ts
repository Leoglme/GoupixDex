import type { CatalogSearchCardHit } from '~/composables/useCardCatalog'
import type { BinderCandidateItem } from '~/types/binders'
import type { BinderPickerItem } from '~/types/binderPicker'
import { filterPickerCandidates, normalize } from '~/composables/useBinderPages'
import { cardThumbFromImage } from '~/utils/catalogAssets'

const CATALOG_MIN_QUERY = 2

/**
 * Fusionne collection + catalogue pour la modale « Ranger une carte ».
 */
export function buildBinderPickerResults(
  candidates: BinderCandidateItem[],
  pockets: Map<string, number>,
  query: string,
  setFilter: string,
  catalogHits: CatalogSearchCardHit[],
): BinderPickerItem[] {
  const fromCollection = filterPickerCandidates(candidates, pockets, query, setFilter).map(
    (c): BinderPickerItem => ({ ...c, source: 'collection' }),
  )

  const needle = normalize(query.trim())
  if (needle.length < CATALOG_MIN_QUERY) {
    return fromCollection
  }

  const ownedTcgIds = new Set(candidates.map((c) => c.tcgdex_card_id))
  const seenCatalog = new Set<string>()
  const fromCatalog: BinderPickerItem[] = []

  for (const hit of catalogHits) {
    if (ownedTcgIds.has(hit.id) || seenCatalog.has(hit.id)) {
      continue
    }
    const setName = hit.set_name?.trim() ?? ''
    if (setFilter && setName !== setFilter) {
      continue
    }
    const label = `${hit.display_name?.trim() || hit.name} ${setName} ${hit.localId}`
    if (!normalize(label).includes(needle)) {
      continue
    }
    seenCatalog.add(hit.id)
    fromCatalog.push({
      source: 'catalog',
      tcgdex_card_id: hit.id,
      card_name: hit.display_name?.trim() || hit.name,
      set_name: setName,
      local_id: hit.localId,
      image_url: cardThumbFromImage(hit.image, hit.image_low) ?? '',
    })
  }

  return [...fromCollection, ...fromCatalog]
}

export { CATALOG_MIN_QUERY }
