/** Types du composant GoupixDexCollectionSectionTabs (onglets Cartes / Produits / Valeur). */

export type CollectionSection = 'cartes' | 'produits' | 'valeur'

export interface GoupixDexCollectionSectionTabsProps {
  /** Section actuellement affichée (surligne l'onglet correspondant). */
  active: CollectionSection
}
