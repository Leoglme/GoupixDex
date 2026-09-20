export type GoupixDexBaseTableAlign = 'left' | 'center' | 'right'

export type GoupixDexBaseTableProps = {
  minWidth?: string
  animateRowMoves?: boolean
}

export type GoupixDexBaseTableThProps = {
  align?: GoupixDexBaseTableAlign
  srOnly?: boolean
}

export type GoupixDexBaseTableSortDirection = 'asc' | 'desc'

export type GoupixDexBaseTableSortThProps = {
  align?: GoupixDexBaseTableAlign
  label: string
  active?: boolean
  direction?: GoupixDexBaseTableSortDirection
  title?: string
  thClass?: string
}

export type GoupixDexBaseTableTdProps = {
  align?: GoupixDexBaseTableAlign
  label?: string
}
