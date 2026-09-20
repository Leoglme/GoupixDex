import type { BinderCandidateItem } from '~/types/binders'

/** Carte déjà dans Ma collection (candidat classeur). */
export type BinderPickerCollectionItem = BinderCandidateItem & { source: 'collection' }

/** Carte trouvée dans le catalogue Pokémon (pas encore possédée). */
export type BinderPickerCatalogItem = {
  source: 'catalog'
  tcgdex_card_id: string
  card_name: string
  set_name: string
  local_id: string
  image_url: string
}

export type BinderPickerItem = BinderPickerCollectionItem | BinderPickerCatalogItem

/**
 *
 * @param item
 */
export function pickerItemKey(item: BinderPickerItem): string {
  return item.source === 'collection' ? `c:${item.collection_card_id}` : `t:${item.tcgdex_card_id}`
}
