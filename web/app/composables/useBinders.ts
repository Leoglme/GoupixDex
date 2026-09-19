/** Thematic binders (classeurs) — REST `/binders`. */

import type { BinderDetail, BinderSummary } from '~/types/binders'

/**
 *
 */
export function useBinders() {
  const { $api } = useNuxtApp()

  /**
   *
   */
  async function listBinders(): Promise<BinderSummary[]> {
    const { data } = await $api.get<{ items: BinderSummary[] }>('/binders')
    return data.items
  }

  /**
   *
   */
  async function getBinder(id: number): Promise<BinderDetail> {
    const { data } = await $api.get<BinderDetail>(`/binders/${id}`)
    return data
  }

  /**
   *
   */
  async function createBinder(name: string): Promise<BinderDetail> {
    const { data } = await $api.post<{ binder: BinderDetail }>('/binders', { name })
    if (!data?.binder?.id) {
      throw new Error('Réponse API invalide après création du classeur')
    }
    return data.binder
  }

  /**
   *
   */
  async function updateBinder(id: number, body: Record<string, unknown>): Promise<BinderDetail> {
    const { data } = await $api.patch<BinderDetail>(`/binders/${id}`, body)
    return data
  }

  /**
   *
   */
  async function deleteBinder(id: number): Promise<void> {
    await $api.delete(`/binders/${id}`)
  }

  /**
   *
   */
  async function reorderBinders(binderIds: number[]): Promise<void> {
    await $api.post('/binders/reorder', { binder_ids: binderIds })
  }

  /**
   *
   */
  async function placeItemInPocket(binderId: number, collectionCardId: number, pocket: number): Promise<BinderDetail> {
    const { data } = await $api.post<BinderDetail>(`/binders/${binderId}/place`, {
      collection_card_id: collectionCardId,
      pocket,
    })
    return data
  }

  /**
   *
   */
  async function movePocket(binderId: number, pocketKey: string, toPocket: number): Promise<BinderDetail> {
    const { data } = await $api.post<BinderDetail>(`/binders/${binderId}/move`, {
      pocket_key: pocketKey,
      to_pocket: toPocket,
    })
    return data
  }

  /**
   *
   */
  async function removeFromPocket(binderId: number, pocketKey: string): Promise<BinderDetail> {
    const { data } = await $api.post<BinderDetail>(`/binders/${binderId}/remove`, {
      pocket_key: pocketKey,
    })
    return data
  }

  /**
   *
   */
  async function setPageCount(binderId: number, pageCount: number): Promise<BinderDetail> {
    const { data } = await $api.post<BinderDetail>(`/binders/${binderId}/page-count`, {
      page_count: pageCount,
    })
    return data
  }

  /**
   *
   */
  async function addItems(binderId: number, collectionCardIds: number[]): Promise<BinderDetail> {
    const { data } = await $api.post<BinderDetail>(`/binders/${binderId}/add-items`, {
      collection_card_ids: collectionCardIds,
    })
    return data
  }

  return {
    listBinders,
    getBinder,
    createBinder,
    updateBinder,
    deleteBinder,
    reorderBinders,
    placeItemInPocket,
    movePocket,
    removeFromPocket,
    setPageCount,
    addItems,
  }
}
