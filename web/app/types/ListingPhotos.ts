import type { ComputedRef, Ref } from 'vue'

export type ListingPhotoSide = 'front' | 'back' | 'extra'

export type ListingPhoto = {
  id: number
  side: ListingPhotoSide
  file: File
  previewUrl: string
}

export type ListingPhotos = {
  photos: ComputedRef<ListingPhoto[]>
  isProcessingPhoto: Ref<boolean>
  setCardSidePhoto: (side: 'front' | 'back', file: File) => Promise<void>
  addExtraPhotos: (files: File[]) => Promise<void>
  removePhoto: (photoId: number) => void
  clearPhotos: () => void
}
