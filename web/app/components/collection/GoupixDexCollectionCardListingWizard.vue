<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="translate-y-6 opacity-0"
      leave-active-class="transition duration-150 ease-in"
      leave-to-class="translate-y-6 opacity-0"
    >
      <div
        v-if="props.open"
        class="fixed inset-0 z-[90] flex items-stretch justify-center bg-(--app-overlay) sm:items-center sm:p-6"
        role="dialog"
        aria-modal="true"
        aria-label="Mettre en ligne"
      >
        <div
          class="sm:border-default flex h-dvh w-full flex-col bg-(--app-surface) sm:h-[min(90dvh,860px)] sm:max-w-lg sm:rounded-2xl sm:border sm:shadow-2xl"
        >
          <div class="border-default flex items-center gap-1 border-b px-2 py-2">
            <button
              v-if="previousStep"
              type="button"
              class="text-muted hover:text-highlighted flex size-10 shrink-0 cursor-pointer items-center justify-center rounded-lg transition-colors hover:bg-(--app-surface-2)"
              aria-label="Étape précédente"
              @click="goToStep(previousStep)"
            >
              <UIcon name="i-lucide-chevron-left" class="size-5" />
            </button>
            <div class="min-w-0 flex-1 px-2">
              <p class="text-muted truncate text-xs">{{ props.card.display_name }}</p>
              <h2 class="text-highlighted truncate text-base leading-tight font-semibold">Mettre en ligne</h2>
            </div>
            <button
              type="button"
              class="text-muted hover:text-highlighted flex size-10 shrink-0 cursor-pointer items-center justify-center rounded-lg transition-colors hover:bg-(--app-surface-2)"
              aria-label="Fermer"
              @click="onCloseRequested"
            >
              <UIcon name="i-lucide-x" class="size-5" />
            </button>
          </div>

          <div class="px-4 pt-3">
            <div class="flex gap-1.5">
              <span
                v-for="(stepOption, stepIndex) in LISTING_STEPS"
                :key="stepOption.step"
                class="h-1 flex-1 rounded-full transition-colors"
                :class="stepIndex <= currentStepIndex ? 'bg-(--app-accent)' : 'bg-(--app-line)'"
              />
            </div>
            <p class="text-muted mt-2 text-xs">
              Étape {{ currentStepIndex + 1 }} sur {{ LISTING_STEPS.length }} · {{ currentStepLabel }}
            </p>
          </div>

          <div v-if="currentStep === 'front' || currentStep === 'back'" class="flex min-h-0 flex-1 flex-col">
            <div class="flex min-h-0 flex-1 flex-col items-center justify-center gap-5 px-6 py-4">
              <div
                class="relative aspect-[63/88] h-full max-h-[52dvh] min-h-40 overflow-hidden rounded-2xl bg-(--app-surface-2)"
                :class="currentCardSidePhoto ? 'shadow-lg' : 'border-2 border-dashed border-(--app-line)'"
              >
                <img
                  v-if="currentCardSidePhoto"
                  :src="currentCardSidePhoto.previewUrl"
                  :alt="currentStep === 'front' ? 'Face avant de la carte' : 'Face arrière de la carte'"
                  class="h-full w-full object-cover"
                />
                <template v-else>
                  <GoupixDexCardImage
                    v-if="currentStep === 'front'"
                    :image-url="props.card.image_url"
                    :tcgdex-card-id="props.card.tcgdex_card_id"
                    img-class="h-full w-full object-cover opacity-20"
                  />
                  <div class="absolute inset-0 flex flex-col items-center justify-center gap-3 p-4 text-center">
                    <span class="app-icon-tile size-14">
                      <UIcon
                        :name="currentStep === 'front' ? 'i-lucide-camera' : 'i-lucide-flip-horizontal-2'"
                        class="size-7 text-(--app-accent)"
                      />
                    </span>
                    <p class="text-highlighted text-sm font-semibold">
                      {{ currentStep === 'front' ? 'Face avant' : 'Face arrière' }}
                    </p>
                  </div>
                </template>
                <div
                  v-if="isProcessingPhoto"
                  class="absolute inset-0 flex items-center justify-center bg-(--app-surface)/70"
                >
                  <UIcon name="i-lucide-loader-circle" class="size-8 animate-spin text-(--app-accent)" />
                </div>
              </div>
              <div class="text-center">
                <p class="text-highlighted text-lg font-semibold">
                  {{ currentStep === 'front' ? 'Photographiez la face avant' : 'Retournez la carte' }}
                </p>
                <p class="text-muted mt-1 text-sm">À plat, bien éclairée, sans reflet sur la carte.</p>
              </div>
            </div>
            <div class="border-default space-y-2 border-t px-4 pt-3 pb-[max(1.5rem,env(safe-area-inset-bottom))]">
              <UButton
                color="primary"
                size="xl"
                block
                icon="i-lucide-camera"
                :loading="isProcessingPhoto"
                @click="openCamera(currentCardSide)"
              >
                {{ currentCardSidePhoto ? 'Reprendre la photo' : 'Prendre la photo' }}
              </UButton>
              <UButton
                v-if="currentCardSidePhoto"
                color="neutral"
                variant="soft"
                size="xl"
                block
                trailing-icon="i-lucide-arrow-right"
                :disabled="isProcessingPhoto"
                @click="goToStep(currentStep === 'front' ? 'back' : 'photos')"
              >
                Continuer
              </UButton>
              <UButton
                v-else
                color="neutral"
                variant="ghost"
                size="lg"
                block
                icon="i-lucide-images"
                :disabled="isProcessingPhoto"
                @click="openGallery(currentCardSide)"
              >
                Choisir dans la galerie
              </UButton>
            </div>
          </div>

          <div v-else-if="currentStep === 'photos'" class="flex min-h-0 flex-1 flex-col">
            <div class="min-h-0 flex-1 overflow-y-auto px-4 py-4">
              <p class="text-highlighted text-lg font-semibold">Vos photos</p>
              <p class="text-muted mt-1 text-sm">Ajoutez d'autres photos si besoin (coins, défauts…), puis validez.</p>
              <div class="mt-4 grid grid-cols-2 gap-3">
                <div
                  v-for="photo in photos"
                  :key="photo.id"
                  class="relative aspect-[3/4] overflow-hidden rounded-xl border border-(--app-line) bg-(--app-surface-2)"
                >
                  <img
                    :src="photo.previewUrl"
                    :alt="LISTING_PHOTO_LABELS[photo.side]"
                    class="h-full w-full object-cover"
                  />
                  <span
                    class="absolute top-2 left-2 rounded-md bg-black/60 px-1.5 py-0.5 text-[11px] font-semibold text-white"
                  >
                    {{ LISTING_PHOTO_LABELS[photo.side] }}
                  </span>
                  <button
                    v-if="photo.side === 'extra'"
                    type="button"
                    class="absolute top-2 right-2 flex size-8 cursor-pointer items-center justify-center rounded-full bg-black/60 text-white"
                    aria-label="Retirer la photo"
                    @click="removePhoto(photo.id)"
                  >
                    <UIcon name="i-lucide-x" class="size-4" />
                  </button>
                  <button
                    v-else
                    type="button"
                    class="absolute right-2 bottom-2 left-2 flex cursor-pointer items-center justify-center gap-1.5 rounded-lg bg-black/60 py-2 text-xs font-semibold text-white"
                    :disabled="isProcessingPhoto"
                    @click="openCamera(photo.side)"
                  >
                    <UIcon name="i-lucide-camera" class="size-3.5" />
                    Reprendre
                  </button>
                </div>
                <button
                  type="button"
                  class="text-muted hover:text-highlighted flex aspect-[3/4] cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-(--app-line) transition-colors disabled:cursor-not-allowed"
                  :disabled="isProcessingPhoto"
                  @click="openExtraPhotosPicker"
                >
                  <UIcon
                    :name="isProcessingPhoto ? 'i-lucide-loader-circle' : 'i-lucide-image-plus'"
                    class="size-7"
                    :class="{ 'animate-spin': isProcessingPhoto }"
                  />
                  <span class="text-sm font-medium">Ajouter une photo</span>
                </button>
              </div>
            </div>
            <div class="border-default border-t px-4 pt-3 pb-[max(1.5rem,env(safe-area-inset-bottom))]">
              <UButton
                color="primary"
                size="xl"
                block
                icon="i-lucide-check"
                :disabled="isProcessingPhoto"
                @click="goToStep('article')"
              >
                Valider les photos
              </UButton>
            </div>
          </div>

          <div v-else class="flex min-h-0 flex-1 flex-col">
            <div class="min-h-0 flex-1 overflow-y-auto px-4 py-4">
              <GoupixDexArticleForm
                v-if="articlePrefill"
                ref="articleFormRef"
                mode="create"
                :loading="isCreatingArticle"
                :show-submit-button="false"
                @submit-create="onSubmitCreate"
              />
              <div v-else-if="articlePrefillError" class="space-y-3 py-16 text-center">
                <UIcon name="i-lucide-cloud-off" class="text-muted mx-auto size-9" />
                <p class="text-highlighted text-sm font-medium">La fiche de l'article n'a pas pu être préparée.</p>
                <p class="text-muted text-xs">{{ articlePrefillError }}</p>
                <UButton color="neutral" variant="soft" icon="i-lucide-rotate-ccw" @click="loadArticlePrefill">
                  Réessayer
                </UButton>
              </div>
              <div v-else class="flex flex-col items-center gap-3 py-16 text-center">
                <UIcon name="i-lucide-loader-circle" class="size-8 animate-spin text-(--app-accent)" />
                <p class="text-muted text-sm">Préparation de la fiche (titre, description, prix)…</p>
              </div>
            </div>
            <div class="border-default border-t px-4 pt-3 pb-[max(1.5rem,env(safe-area-inset-bottom))]">
              <UButton
                color="primary"
                size="xl"
                block
                icon="i-lucide-send"
                :loading="isCreatingArticle"
                :disabled="!articlePrefill"
                @click="articleFormRef?.submit()"
              >
                Créer l'article
              </UButton>
            </div>
          </div>

          <input
            ref="cameraInputRef"
            type="file"
            accept="image/*"
            capture="environment"
            class="hidden"
            @change="onCardSidePhotoPicked"
          />
          <input ref="galleryInputRef" type="file" accept="image/*" class="hidden" @change="onCardSidePhotoPicked" />
          <input
            ref="extraPhotosInputRef"
            type="file"
            accept="image/*"
            multiple
            class="hidden"
            @change="onExtraPhotosPicked"
          />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType, Ref } from 'vue'
import type { Article } from '~/composables/useArticles'
import type { CollectionArticlePrefillResponse, CollectionCard } from '~/composables/useCollection'
import type {
  ArticleCreateFormHandle,
  CollectionCardListingStep,
  CollectionCardListingStepOption,
  GoupixDexCollectionCardListingWizardProps,
} from '~/types/GoupixDexCollectionCardListingWizard'
import type { ListingPhoto, ListingPhotos, ListingPhotoSide } from '~/types/ListingPhotos'
import { useDesktopWorkers } from '~/composables/useDesktopWorkers'
import { useListingPhotos } from '~/composables/useListingPhotos'

const props: GoupixDexCollectionCardListingWizardProps = defineProps({
  open: {
    type: Boolean,
    default: false,
  },
  card: {
    type: Object as PropType<CollectionCard>,
    required: true,
  },
})

const emit = defineEmits<{
  close: []
  created: [article: Article]
}>()

const { prepareArticlePrefill } = useCollection()
const { createArticle, publishArticleToVinted } = useArticles()
const { canUseDesktopWorkers } = useDesktopWorkers()
const { openArticle } = useOpenArticleDrawer()
const { confirm: confirmAction } = useGoupixConfirm()
const toast = useToast()
const { photos, isProcessingPhoto, setCardSidePhoto, addExtraPhotos, removePhoto, clearPhotos }: ListingPhotos =
  useListingPhotos()

const LISTING_STEPS: CollectionCardListingStepOption[] = [
  { step: 'front', label: 'Face avant' },
  { step: 'back', label: 'Face arrière' },
  { step: 'photos', label: 'Vos photos' },
  { step: 'article', label: "Fiche de l'article" },
]
const LISTING_PHOTO_LABELS: Record<ListingPhotoSide, string> = {
  front: 'Face avant',
  back: 'Face arrière',
  extra: 'Photo en plus',
}

let pickedCardSide: 'front' | 'back' = 'front'

const currentStep: Ref<CollectionCardListingStep> = ref('front')
const articlePrefill: Ref<CollectionArticlePrefillResponse | null> = ref(null)
const articlePrefillError: Ref<string | null> = ref(null)
const isCreatingArticle: Ref<boolean> = ref(false)
const articleFormRef: Ref<ArticleCreateFormHandle | null> = ref(null)
const cameraInputRef: Ref<HTMLInputElement | null> = ref(null)
const galleryInputRef: Ref<HTMLInputElement | null> = ref(null)
const extraPhotosInputRef: Ref<HTMLInputElement | null> = ref(null)

const currentStepIndex: ComputedRef<number> = computed((): number =>
  LISTING_STEPS.findIndex((stepOption: CollectionCardListingStepOption): boolean => {
    return stepOption.step === currentStep.value
  }),
)

const currentStepLabel: ComputedRef<string> = computed((): string => LISTING_STEPS[currentStepIndex.value]?.label ?? '')

const previousStep: ComputedRef<CollectionCardListingStep | null> = computed(
  (): CollectionCardListingStep | null => LISTING_STEPS[currentStepIndex.value - 1]?.step ?? null,
)

const currentCardSide: ComputedRef<'front' | 'back'> = computed((): 'front' | 'back' =>
  currentStep.value === 'back' ? 'back' : 'front',
)

const currentCardSidePhoto: ComputedRef<ListingPhoto | null> = computed(
  (): ListingPhoto | null =>
    photos.value.find((photo: ListingPhoto): boolean => photo.side === currentCardSide.value) ?? null,
)

/**
 * Affiche une étape de la mise en ligne.
 * @param {CollectionCardListingStep} step - Étape à afficher.
 * @returns {void}
 */
function goToStep(step: CollectionCardListingStep): void {
  currentStep.value = step
}

/**
 * Prépare la fiche de l'article (titre, description, prix conseillé) pendant que les photos se prennent.
 * @returns {Promise<void>} Résolue quand la fiche est prête ou que l'échec est affiché.
 */
async function loadArticlePrefill(): Promise<void> {
  articlePrefillError.value = null
  try {
    articlePrefill.value = await prepareArticlePrefill(props.card.id, true)
  } catch (error: unknown) {
    articlePrefillError.value = apiErrorMessage(error)
  }
}

/**
 * Ouvre l'appareil photo pour une face de la carte (ou une photo en plus).
 * @param {ListingPhotoSide} side - Photo à prendre.
 * @returns {void}
 */
function openCamera(side: ListingPhotoSide): void {
  if (side === 'extra') {
    openExtraPhotosPicker()
    return
  }
  pickedCardSide = side
  cameraInputRef.value?.click()
}

/**
 * Ouvre la galerie pour choisir la photo d'une face de la carte.
 * @param {'front' | 'back'} side - Face à illustrer.
 * @returns {void}
 */
function openGallery(side: 'front' | 'back'): void {
  pickedCardSide = side
  galleryInputRef.value?.click()
}

/**
 * Ouvre le choix des photos en plus (appareil photo ou galerie, plusieurs à la fois).
 * @returns {void}
 */
function openExtraPhotosPicker(): void {
  extraPhotosInputRef.value?.click()
}

/**
 * Enregistre la photo d'une face puis passe à la suite : face arrière, ou récapitulatif des photos.
 * @param {Event} event - Changement du champ fichier.
 * @returns {Promise<void>} Résolue quand la photo est prête.
 */
async function onCardSidePhotoPicked(event: Event): Promise<void> {
  const input: HTMLInputElement = event.target as HTMLInputElement
  const file: File | undefined = input.files?.[0]
  input.value = ''
  if (!file) {
    return
  }
  const side: 'front' | 'back' = pickedCardSide
  await setCardSidePhoto(side, file)
  const hasBackPhoto: boolean = photos.value.some((photo: ListingPhoto): boolean => photo.side === 'back')
  if (currentStep.value === 'front' && side === 'front') {
    goToStep(hasBackPhoto ? 'photos' : 'back')
  } else if (currentStep.value === 'back' && side === 'back') {
    goToStep('photos')
  }
}

/**
 * Ajoute les photos en plus choisies.
 * @param {Event} event - Changement du champ fichier.
 * @returns {Promise<void>} Résolue quand les photos sont prêtes.
 */
async function onExtraPhotosPicked(event: Event): Promise<void> {
  const input: HTMLInputElement = event.target as HTMLInputElement
  const files: File[] = Array.from(input.files ?? [])
  input.value = ''
  if (files.length) {
    await addExtraPhotos(files)
  }
}

/**
 * Crée l'article de la carte avec ses photos, puis ouvre l'article (ou le journal Vinted quand le PC publie).
 * @param {FormData} formData - Corps multipart construit par le formulaire.
 * @returns {Promise<void>} Résolue quand l'article est créé ou l'échec affiché.
 */
async function onSubmitCreate(formData: FormData): Promise<void> {
  if (!canUseDesktopWorkers.value) {
    formData.set('publish_to_vinted', 'false')
  }
  formData.set('collection_card_id', String(props.card.id))
  isCreatingArticle.value = true
  try {
    const { article, vinted } = await createArticle(formData)
    emit('created', article)
    if (canUseDesktopWorkers.value && vinted.desktop_local && vinted.stream_path) {
      try {
        await publishArticleToVinted(article.id)
      } catch (error: unknown) {
        toast.add({ title: 'Worker Vinted', description: apiErrorMessage(error), color: 'error' })
        await navigateTo('/articles')
        return
      }
      await navigateTo({ path: '/articles/listing-logs', query: { article: String(article.id), progress: 'local' } })
      return
    }
    toast.add({ title: 'Article créé', description: 'Publiez-le sur vos marketplaces.', color: 'success' })
    openArticle(article.id)
  } catch (error: unknown) {
    toast.add({ title: 'Création impossible', description: apiErrorMessage(error), color: 'error' })
  } finally {
    isCreatingArticle.value = false
  }
}

/**
 * Ferme la mise en ligne, après confirmation quand des photos seraient perdues.
 * @returns {Promise<void>} Résolue une fois la fenêtre fermée ou la fermeture annulée.
 */
async function onCloseRequested(): Promise<void> {
  if (photos.value.length) {
    const isDiscardConfirmed: boolean = await confirmAction({
      title: 'Abandonner la mise en ligne ?',
      description: 'Les photos prises seront perdues.',
      confirmLabel: 'Abandonner',
      cancelLabel: 'Continuer',
      confirmColor: 'error',
    })
    if (!isDiscardConfirmed) {
      return
    }
  }
  emit('close')
}

watch(
  (): boolean => props.open,
  (isOpen: boolean): void => {
    if (!isOpen) {
      return
    }
    clearPhotos()
    currentStep.value = 'front'
    articlePrefill.value = null
    loadArticlePrefill()
  },
  { immediate: true },
)

watch(articleFormRef, async (articleForm: ArticleCreateFormHandle | null): Promise<void> => {
  if (!articleForm || !articlePrefill.value) {
    return
  }
  // Les vraies photos remplacent l'image officielle de la carte que le préremplissage ajouterait.
  await articleForm.applyCatalogPrefill({ ...articlePrefill.value, image_url_high: null })
  articleForm.addImageFiles(photos.value.map((photo: ListingPhoto): File => photo.file))
})
</script>
