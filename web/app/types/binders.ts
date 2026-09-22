import type { BinderDesign } from '~/utils/binder/binder-design'

export interface BinderCoverItem {
  image_url: string
}

export interface BinderSummary {
  id: number
  name: string
  color: string | null
  style: string
  page_grid: string
  page_count: number
  pokedex_region: string | null
  pokedex_slots: Record<string, number> | null
  position: number | null
  design: unknown
  cover: unknown
  cover_collection_card_ids: number[] | null
  created_at: string | null
  updated_at: string | null
  card_count: number
  estimated_value_eur: number | null
  total_value_eur: number | null
  pokedex_owned: number | null
  pokedex_total: number | null
  covers: BinderCoverItem[]
}

export interface BinderPocketItem {
  id: string
  kind: 'owned' | 'wanted'
  collection_card_id: number
  card_name: string
  set_name?: string | null
  local_id?: string | null
  tcgdex_card_id?: string | null
  image_url: string
  quantity: number
  position: number | null
  created_at: string
}

export interface BinderCandidateItem {
  id: string
  collection_card_id: number
  tcgdex_card_id: string
  card_name: string
  set_name: string
  local_id: string
  image_url: string
  quantity: number
  in_binder: boolean
}

export interface BinderDetail extends BinderSummary {
  items: BinderPocketItem[]
  candidates: BinderCandidateItem[]
  cover_urls?: Record<string, string>
}

export type BinderDesignResolved = BinderDesign
