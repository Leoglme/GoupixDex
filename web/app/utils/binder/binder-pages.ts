// Pages de pochettes d'un classeur — formats de feuilles et rangement.
// `binder_items.position` est le numéro de pochette absolu : page = position
// ÷ pochettes par page, trous permis (pochettes vides).

export const PAGE_GRIDS = [
  { code: '3x3', cols: 3, rows: 3, label: '9 pochettes' },
  { code: '4x3', cols: 4, rows: 3, label: '12 pochettes' },
  { code: '2x2', cols: 2, rows: 2, label: '4 pochettes' },
  { code: '4x4', cols: 4, rows: 4, label: '16 pochettes' },
] as const

export type PageGrid = (typeof PAGE_GRIDS)[number]
export type PageGridCode = PageGrid['code']

export function pageGrid(code: string | null | undefined): PageGrid {
  return PAGE_GRIDS.find((g) => g.code === code) ?? PAGE_GRIDS[0]
}

export function pocketsPerPage(grid: PageGrid): number {
  return grid.cols * grid.rows
}

/**
 * Pochette de chaque carte. Les positions valides sont conservées ; une
 * carte sans position ou en collision prend la première pochette libre.
 */
export function layoutPockets(
  items: { id: string; position: number | null; created_at: string }[],
): Map<string, number> {
  const taken = new Set<number>()
  const pockets = new Map<string, number>()
  const pending: typeof items = []
  const sorted = [...items].sort(
    (a, b) =>
      (a.position ?? Number.MAX_SAFE_INTEGER) - (b.position ?? Number.MAX_SAFE_INTEGER) ||
      b.created_at.localeCompare(a.created_at),
  )
  for (const item of sorted) {
    const p = item.position
    if (p != null && p >= 0 && !taken.has(p)) {
      taken.add(p)
      pockets.set(item.id, p)
    } else {
      pending.push(item)
    }
  }
  let cursor = 0
  for (const item of pending) {
    while (taken.has(cursor)) cursor++
    taken.add(cursor)
    pockets.set(item.id, cursor)
  }
  return pockets
}
