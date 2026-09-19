// Styles de couverture des classeurs — le rendu et le nombre de cartes
// de couverture s'adaptent au style choisi
export const BINDER_STYLES = [
  {
    code: 'binder',
    label: 'Classeur',
    description: 'Tranche perforée et page de pochettes',
    covers: 4,
  },
  {
    code: 'mosaic',
    label: 'Mosaïque',
    description: 'Quatre cartes en grille, sans décor',
    covers: 4,
  },
  {
    code: 'showcase',
    label: 'Vitrine',
    description: 'Une carte star mise en avant',
    covers: 1,
  },
  {
    code: 'fan',
    label: 'Éventail',
    description: 'Trois cartes en éventail',
    covers: 3,
  },
  {
    code: 'label',
    label: 'Étiquette',
    description: 'Couverture pleine couleur, sans cartes',
    covers: 0,
  },
  {
    code: 'custom',
    label: 'Sur mesure',
    description: 'Composition personnalisée (v2)',
    covers: 0,
  },
] as const

export type BinderStyle = (typeof BINDER_STYLES)[number]['code']

export function binderStyle(code: string | null | undefined): BinderStyle {
  return (BINDER_STYLES.find((s) => s.code === code)?.code ?? 'binder') as BinderStyle
}

export function binderStyleCovers(code: string | null | undefined): number {
  return BINDER_STYLES.find((s) => s.code === code)?.covers ?? 4
}
