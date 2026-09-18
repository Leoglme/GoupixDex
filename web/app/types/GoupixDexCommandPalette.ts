// app/types/GoupixDexCommandPalette.ts

/**
 * One selectable row of the command palette.
 */
export type GoupixDexCommandPaletteAction = {
  id: string
  label: string
  icon: string
  /** Small right-aligned hint (city, set, price…). */
  meta?: string
  /** Extra searchable text beyond the label. */
  keywords?: string
  /** Position in the flat keyboard-navigation list. */
  flatIndex: number
  run: () => void
}

/**
 * One titled group of palette rows.
 */
export type GoupixDexCommandPaletteGroup = {
  key: string
  heading: string
  items: GoupixDexCommandPaletteAction[]
}
