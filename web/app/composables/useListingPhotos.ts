import type { ComputedRef, Ref } from 'vue'
import type { ListingPhoto, ListingPhotos, ListingPhotoSide } from '~/types/ListingPhotos'

const LISTING_PHOTO_MAX_EDGE_PX: number = 2048
const LISTING_PHOTO_JPEG_QUALITY: number = 0.86
const LISTING_PHOTO_SIDE_ORDER: Record<ListingPhotoSide, number> = { front: 0, back: 1, extra: 2 }

/**
 * Réduit une photo d'appareil (12 Mpx, plusieurs Mo) à 2048 px de côté en JPEG, en gardant son orientation.
 * @param {File} file - Photo prise ou choisie dans la galerie.
 * @returns {Promise<File>} Photo réduite, ou l'originale quand le navigateur ne sait pas la décoder (HEIC hors Safari).
 */
async function shrinkListingPhoto(file: File): Promise<File> {
  const objectUrl: string = URL.createObjectURL(file)
  try {
    const image: HTMLImageElement = new Image()
    image.src = objectUrl
    await image.decode()
    const scale: number = Math.min(1, LISTING_PHOTO_MAX_EDGE_PX / Math.max(image.naturalWidth, image.naturalHeight))
    const canvas: HTMLCanvasElement = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(image.naturalWidth * scale))
    canvas.height = Math.max(1, Math.round(image.naturalHeight * scale))
    const context: CanvasRenderingContext2D | null = canvas.getContext('2d')
    if (!context) {
      return file
    }
    context.drawImage(image, 0, 0, canvas.width, canvas.height)
    const blob: Blob | null = await new Promise((resolve: (value: Blob | null) => void): void => {
      canvas.toBlob(resolve, 'image/jpeg', LISTING_PHOTO_JPEG_QUALITY)
    })
    if (!blob) {
      return file
    }
    const baseName: string = file.name.replace(/\.[^.]+$/, '') || 'photo'
    return new File([blob], `${baseName}.jpg`, { type: 'image/jpeg' })
  } catch {
    return file
  } finally {
    URL.revokeObjectURL(objectUrl)
  }
}

/**
 * Photos d'une annonce en cours de préparation : face avant, face arrière puis photos en plus, réduites pour l'envoi.
 * @returns {ListingPhotos} Photos dans l'ordre de l'annonce et actions pour les prendre, remplacer ou retirer.
 */
export function useListingPhotos(): ListingPhotos {
  const storedPhotos: Ref<ListingPhoto[]> = ref([])
  const isProcessingPhoto: Ref<boolean> = ref(false)

  let nextPhotoId: number = 1

  const photos: ComputedRef<ListingPhoto[]> = computed((): ListingPhoto[] =>
    [...storedPhotos.value].sort(
      (first: ListingPhoto, second: ListingPhoto): number =>
        LISTING_PHOTO_SIDE_ORDER[first.side] - LISTING_PHOTO_SIDE_ORDER[second.side] || first.id - second.id,
    ),
  )

  /**
   * Réduit une photo et prépare son aperçu.
   * @param {ListingPhotoSide} side - Face de la carte, ou photo en plus.
   * @param {File} file - Photo d'origine.
   * @returns {Promise<ListingPhoto>} Photo prête à être affichée et envoyée.
   */
  async function buildListingPhoto(side: ListingPhotoSide, file: File): Promise<ListingPhoto> {
    const shrunkFile: File = await shrinkListingPhoto(file)
    const photo: ListingPhoto = { id: nextPhotoId, side, file: shrunkFile, previewUrl: URL.createObjectURL(shrunkFile) }
    nextPhotoId += 1
    return photo
  }

  /**
   * Enregistre (ou remplace) la photo d'une face de la carte.
   * @param {'front' | 'back'} side - Face photographiée.
   * @param {File} file - Photo prise ou choisie.
   * @returns {Promise<void>} Résolue quand la photo est prête.
   */
  async function setCardSidePhoto(side: 'front' | 'back', file: File): Promise<void> {
    isProcessingPhoto.value = true
    try {
      const photo: ListingPhoto = await buildListingPhoto(side, file)
      const replacedPhoto: ListingPhoto | undefined = storedPhotos.value.find(
        (storedPhoto: ListingPhoto): boolean => storedPhoto.side === side,
      )
      if (replacedPhoto) {
        URL.revokeObjectURL(replacedPhoto.previewUrl)
      }
      storedPhotos.value = [
        ...storedPhotos.value.filter((storedPhoto: ListingPhoto): boolean => storedPhoto.side !== side),
        photo,
      ]
    } finally {
      isProcessingPhoto.value = false
    }
  }

  /**
   * Ajoute des photos en plus des deux faces (coins, défauts…).
   * @param {File[]} files - Photos prises ou choisies.
   * @returns {Promise<void>} Résolue quand toutes les photos sont prêtes.
   */
  async function addExtraPhotos(files: File[]): Promise<void> {
    isProcessingPhoto.value = true
    try {
      const extraPhotos: ListingPhoto[] = []
      for (const file of files) {
        extraPhotos.push(await buildListingPhoto('extra', file))
      }
      storedPhotos.value = [...storedPhotos.value, ...extraPhotos]
    } finally {
      isProcessingPhoto.value = false
    }
  }

  /**
   * Retire une photo de l'annonce.
   * @param {number} photoId - Photo à retirer.
   * @returns {void}
   */
  function removePhoto(photoId: number): void {
    const removedPhoto: ListingPhoto | undefined = storedPhotos.value.find(
      (storedPhoto: ListingPhoto): boolean => storedPhoto.id === photoId,
    )
    if (removedPhoto) {
      URL.revokeObjectURL(removedPhoto.previewUrl)
    }
    storedPhotos.value = storedPhotos.value.filter((storedPhoto: ListingPhoto): boolean => storedPhoto.id !== photoId)
  }

  /**
   * Oublie toutes les photos et libère leurs aperçus.
   * @returns {void}
   */
  function clearPhotos(): void {
    for (const storedPhoto of storedPhotos.value) {
      URL.revokeObjectURL(storedPhoto.previewUrl)
    }
    storedPhotos.value = []
  }

  onBeforeUnmount((): void => {
    clearPhotos()
  })

  return { photos, isProcessingPhoto, setCardSidePhoto, addExtraPhotos, removePhoto, clearPhotos }
}
