// Palette des tranches de classeur — codes stockés en base, hex au rendu
export const BINDER_COLORS = [
  { code: 'red', hex: '#dc2626', label: 'Rouge' },
  { code: 'orange', hex: '#ea580c', label: 'Orange' },
  { code: 'yellow', hex: '#ca8a04', label: 'Jaune' },
  { code: 'green', hex: '#16a34a', label: 'Vert' },
  { code: 'blue', hex: '#2563eb', label: 'Bleu' },
  { code: 'purple', hex: '#7c3aed', label: 'Violet' },
  { code: 'pink', hex: '#db2777', label: 'Rose' },
] as const

export type BinderColor = (typeof BINDER_COLORS)[number]['code']

export function binderColorHex(code: string | null | undefined): string | null {
  return BINDER_COLORS.find((c) => c.code === code)?.hex ?? null
}
