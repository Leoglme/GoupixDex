<script setup lang="ts">
import type { Article, ArticleUpdateBody } from '~/composables/useArticles'
import type { AppSettings } from '~/composables/useSettings'
import type { WardrobeSlotPrefill } from '~/composables/useWardrobeImportPrefill'
import { EBAY_GRADE_OPTIONS, EBAY_PROFESSIONAL_GRADER_OPTIONS } from '~/utils/ebayTradingCardGrading'

const props = withDefaults(
  defineProps<{
    mode: 'create' | 'edit'
    article?: Article | null
    loading?: boolean
    /** Text shown under the button while loading (e.g. waiting on Vinted). */
    loadingHint?: string | null
    /** Hide the "Publish on Vinted" checkbox (e.g. batch create with a global option). */
    hideVintedOption?: boolean
    /** Show the form submit button (disable if the parent handles submit). */
    showSubmitButton?: boolean
  }>(),
  {
    hideVintedOption: false,
    showSubmitButton: true
  }
)

const emit = defineEmits<{
  submitCreate: [form: FormData]
  submitEdit: [body: ArticleUpdateBody]
}>()

const title = ref('')
const description = ref('')
const pokemonName = ref('')
const setCode = ref('')
const cardNumber = ref('')
const conditionOptions: { label: string, value: string }[] = [
  { label: 'Mint', value: 'Mint' },
  { label: 'Near Mint', value: 'Near Mint' },
  { label: 'Excellent', value: 'Excellent' },
  { label: 'Good', value: 'Good' },
  { label: 'Played', value: 'Played' }
]

const condition = ref('Near Mint')
const isGraded = ref(false)
const gradedGraderValueId = ref('')
const gradedGradeValueId = ref('')
const gradedCertNumber = ref('')
const purchasePrice = ref('')
const sellPrice = ref('')
const toast = useToast()

const imageFiles = ref<File[]>([])
const previews = ref<string[]>([])
/** Opt-in Vinted publish (create only, off by default). */
const publishToVinted = ref(false)
/** Publier sur eBay à la création (si le canal est prêt). */
const publishToEbay = ref(false)
const svcSettings = ref<AppSettings | null>(null)
const { getSettings } = useSettings()
/** Vinted wardrobe import (create): sold status + date on API side. */
const importIsSold = ref(false)
const importSoldAt = ref<string | null>(null)
/** Import garde-robe : annonce déjà sur Vinted (active ou vendue). */
const wardrobeVintedListed = ref(false)
const wardrobeVintedPublishedAtIso = ref<string | null>(null)
/** Prix réalisé importé (ventes Vinted). */
const wardrobeImportSoldPrice = ref<string | null>(null)
const { isDesktopApp } = useDesktopRuntime()
const { fetchBlob: fetchVintedListingImageBlob } = useVintedListingImage()
const canUseVinted = computed(
  () => isDesktopApp.value && !importIsSold.value && (svcSettings.value?.vinted_enabled !== false)
)
const showEbayPublish = computed(
  () =>
    !importIsSold.value
    && svcSettings.value?.ebay_enabled === true
    && svcSettings.value?.ebay_oauth_configured === true
)
const canPublishEbay = computed(
  () =>
    showEbayPublish.value
    && svcSettings.value?.ebay_connected === true
    && svcSettings.value?.ebay_listing_config_complete === true
)

onMounted(async () => {
  try {
    svcSettings.value = await getSettings()
  } catch {
    svcSettings.value = null
  }
})

async function blobFromVintedPhotoUrl(url: string): Promise<Blob | null> {
  try {
    const res = await fetch(url)
    if (res.ok) {
      return await res.blob()
    }
  } catch {
    /* CORS ou réseau */
  }
  if (isDesktopApp.value) {
    try {
      return await fetchVintedListingImageBlob(url)
    } catch {
      return null
    }
  }
  return null
}

watch(
  () => props.article,
  (a) => {
    if (!a) {
      return
    }
    title.value = a.title
    description.value = a.description
    pokemonName.value = a.pokemon_name ?? ''
    setCode.value = a.set_code ?? ''
    cardNumber.value = a.card_number ?? ''
    condition.value =
      a.condition && conditionOptions.some((o) => o.value === a.condition)
        ? a.condition
        : 'Near Mint'
    purchasePrice.value = String(a.purchase_price)
    sellPrice.value = a.sell_price != null ? String(a.sell_price) : ''
    isGraded.value = Boolean(a.is_graded)
    gradedGraderValueId.value =
      a.graded_grader_value_id
      && EBAY_PROFESSIONAL_GRADER_OPTIONS.some(o => o.value === a.graded_grader_value_id)
        ? a.graded_grader_value_id
        : ''
    gradedGradeValueId.value =
      a.graded_grade_value_id
      && EBAY_GRADE_OPTIONS.some(o => o.value === a.graded_grade_value_id)
        ? a.graded_grade_value_id
        : ''
    gradedCertNumber.value = a.graded_cert_number ?? ''
  },
  { immediate: true }
)

function onFiles(e: Event) {
  const input = e.target as HTMLInputElement
  const files = input.files
  if (!files?.length) {
    return
  }
  for (const f of Array.from(files)) {
    imageFiles.value.push(f)
    previews.value.push(URL.createObjectURL(f))
  }
  input.value = ''
}

function removePreview(i: number) {
  URL.revokeObjectURL(previews.value[i]!)
  previews.value.splice(i, 1)
  imageFiles.value.splice(i, 1)
}

/** Append image files (e.g. same file as OCR scan). */
function addImageFiles(files: File[]) {
  for (const f of files) {
    imageFiles.value.push(f)
    previews.value.push(URL.createObjectURL(f))
  }
}

function applyScanPrefill(scan: {
  listing_preview: { title: string, description: string, suggested_price: number | null }
  ocr: Record<string, unknown>
  pricing: { cardmarket_eur: number | null, tcgplayer_usd: number | null }
}) {
  title.value = scan.listing_preview.title
  description.value = scan.listing_preview.description
  const o = scan.ocr
  const en = typeof o.pokemon_name_english === 'string' ? o.pokemon_name_english : ''
  const fr = typeof o.pokemon_name === 'string' ? o.pokemon_name : ''
  pokemonName.value = en || fr
  setCode.value = typeof o.set_code === 'string' ? o.set_code : ''
  cardNumber.value = typeof o.card_number === 'string' ? o.card_number : ''
  if (scan.listing_preview.suggested_price != null) {
    purchasePrice.value = String(scan.listing_preview.suggested_price)
  }
  isGraded.value = false
  gradedGraderValueId.value = ''
  gradedGradeValueId.value = ''
  gradedCertNumber.value = ''
  importIsSold.value = false
  importSoldAt.value = null
  wardrobeVintedListed.value = false
  wardrobeVintedPublishedAtIso.value = null
  wardrobeImportSoldPrice.value = null
}

/**
 * Prefill used by the market-search page (``/market``): we only know a subset
 * of the fields (title, price, condition, …) and optionally a remote image URL
 * that we try to fetch as a File so it is bundled with the article creation.
 */
async function applyEbayPrefill(p: {
  title?: string
  description?: string
  pokemonName?: string
  setCode?: string
  cardNumber?: string
  condition?: string
  purchasePrice?: string
  sellPrice?: string
  imageUrl?: string | null
}) {
  if (p.title) {
    title.value = p.title
  }
  if (p.description) {
    description.value = p.description
  }
  if (p.pokemonName) {
    pokemonName.value = p.pokemonName
  }
  if (p.setCode) {
    setCode.value = p.setCode
  }
  if (p.cardNumber) {
    cardNumber.value = p.cardNumber
  }
  if (p.condition && conditionOptions.some(o => o.value === p.condition)) {
    condition.value = p.condition
  }
  if (p.purchasePrice) {
    purchasePrice.value = p.purchasePrice
  }
  if (p.sellPrice) {
    sellPrice.value = p.sellPrice
  }
  if (p.imageUrl) {
    try {
      const blob = await blobFromVintedPhotoUrl(p.imageUrl)
      if (blob) {
        const ext = blob.type.includes('png') ? 'png' : 'jpg'
        const file = new File([blob], `ebay-${Date.now()}.${ext}`, {
          type: blob.type || 'image/jpeg'
        })
        addImageFiles([file])
      }
    } catch {
      /* image facultative : on ignore si le téléchargement échoue (CORS) */
    }
  }
}

async function applyWardrobeSlot(p: WardrobeSlotPrefill) {
  while (previews.value.length) {
    removePreview(0)
  }
  importIsSold.value = p.isSold
  importSoldAt.value = p.soldAt
  wardrobeVintedListed.value = p.wardrobeVintedListed
  wardrobeVintedPublishedAtIso.value = p.vintedPublishedAtIso
  wardrobeImportSoldPrice.value = p.importSoldPrice
  title.value = p.title
  description.value = p.description
  purchasePrice.value = p.purchasePrice || '0'
  sellPrice.value = p.sellPrice
  pokemonName.value = p.pokemonName
  setCode.value = p.setCode
  cardNumber.value = p.cardNumber
  condition.value = conditionOptions.some(o => o.value === p.condition)
    ? p.condition
    : 'Near Mint'
  publishToVinted.value = false
  publishToEbay.value = false
  isGraded.value = false
  gradedGraderValueId.value = ''
  gradedGradeValueId.value = ''
  gradedCertNumber.value = ''

  for (let i = 0; i < p.photoUrls.length; i++) {
    const url = p.photoUrls[i]!
    try {
      const blob = await blobFromVintedPhotoUrl(url)
      if (!blob) {
        continue
      }
      const ext = blob.type.includes('png') ? 'png' : 'jpg'
      const file = new File([blob], `vinted-${i}.${ext}`, {
        type: blob.type || 'image/jpeg'
      })
      addImageFiles([file])
    } catch {
      /* image optionnelle */
    }
  }
}

defineExpose({
  applyScanPrefill,
  addImageFiles,
  buildCreateFormData,
  applyWardrobeSlot,
  applyEbayPrefill
})

function buildCreateFormData(): FormData {
  const fd = new FormData()
  fd.append('title', title.value.trim())
  fd.append('description', description.value)
  fd.append('purchase_price', purchasePrice.value.trim())
  fd.append('condition', condition.value.trim() || 'Near Mint')
  fd.append('is_graded', isGraded.value ? 'true' : 'false')
  if (isGraded.value) {
    if (gradedGraderValueId.value) {
      fd.append('graded_grader_value_id', gradedGraderValueId.value)
    }
    if (gradedGradeValueId.value) {
      fd.append('graded_grade_value_id', gradedGradeValueId.value)
    }
    if (gradedCertNumber.value.trim()) {
      fd.append('graded_cert_number', gradedCertNumber.value.trim().slice(0, 30))
    }
  }
  if (pokemonName.value.trim()) {
    fd.append('pokemon_name', pokemonName.value.trim())
  }
  if (setCode.value.trim()) {
    fd.append('set_code', setCode.value.trim())
  }
  if (cardNumber.value.trim()) {
    fd.append('card_number', cardNumber.value.trim())
  }
  if (sellPrice.value.trim()) {
    fd.append('sell_price', sellPrice.value.trim())
  }
  for (const f of imageFiles.value) {
    fd.append('images', f)
  }
  fd.append('publish_to_vinted', canUseVinted.value && publishToVinted.value ? 'true' : 'false')
  fd.append('publish_to_ebay', canPublishEbay.value && publishToEbay.value ? 'true' : 'false')
  fd.append('is_sold', importIsSold.value ? 'true' : 'false')
  if (importIsSold.value && importSoldAt.value) {
    fd.append('sold_at', importSoldAt.value)
  }
  if (wardrobeVintedListed.value) {
    fd.append('wardrobe_vinted_listed', 'true')
    if (wardrobeVintedPublishedAtIso.value) {
      fd.append('vinted_published_at', wardrobeVintedPublishedAtIso.value)
    }
  }
  if (importIsSold.value && wardrobeVintedListed.value) {
    fd.append('sale_source', 'vinted')
    if (wardrobeImportSoldPrice.value?.trim()) {
      fd.append('sold_price', wardrobeImportSoldPrice.value.trim())
    }
  }
  return fd
}

const config = useRuntimeConfig()

function imageSrc(url: string) {
  if (url.startsWith('http')) {
    return url
  }
  return `${config.public.apiBase}${url}`
}

function submit() {
  if (isGraded.value) {
    if (!gradedGraderValueId.value || !gradedGradeValueId.value) {
      toast.add({
        title: 'Carte gradée',
        description: 'Choisissez une société de grading et une note (requis pour eBay).',
        color: 'error'
      })
      return
    }
  }
  if (props.mode === 'create') {
    emit('submitCreate', buildCreateFormData())
    return
  }
  emit('submitEdit', {
    title: title.value.trim(),
    description: description.value,
    pokemon_name: pokemonName.value.trim() || null,
    set_code: setCode.value.trim() || null,
    card_number: cardNumber.value.trim() || null,
    condition: condition.value.trim() || 'Near Mint',
    is_graded: isGraded.value,
    graded_grader_value_id: isGraded.value ? gradedGraderValueId.value : null,
    graded_grade_value_id: isGraded.value ? gradedGradeValueId.value : null,
    graded_cert_number: isGraded.value && gradedCertNumber.value.trim()
      ? gradedCertNumber.value.trim().slice(0, 30)
      : null,
    purchase_price: Number(purchasePrice.value.replace(',', '.')),
    sell_price: sellPrice.value.trim()
      ? Number(sellPrice.value.replace(',', '.'))
      : null
  })
}
</script>

<template>
  <div class="space-y-6">
    <div class="grid gap-4 sm:grid-cols-2">
      <UFormField label="Titre" required>
        <UInput v-model="title" class="w-full" />
      </UFormField>
      <UFormField v-if="!isGraded" label="État">
        <USelect
          v-model="condition"
          :items="conditionOptions"
          value-key="value"
          label-key="label"
          class="w-full"
        />
      </UFormField>
    </div>
    <UCheckbox
      v-model="isGraded"
      label="Carte gradée (slab — PSA, CGC, BGS…)"
      class="mt-1"
    />
    <div v-if="isGraded" class="space-y-4 rounded-lg border border-default p-4">
      <div class="grid gap-4 sm:grid-cols-2">
        <UFormField label="Société de grading" required>
          <USelect
            v-model="gradedGraderValueId"
            :items="EBAY_PROFESSIONAL_GRADER_OPTIONS"
            value-key="value"
            label-key="label"
            class="w-full"
            placeholder="Choisir…"
          />
        </UFormField>
        <UFormField label="Note" required>
          <USelect
            v-model="gradedGradeValueId"
            :items="EBAY_GRADE_OPTIONS"
            value-key="value"
            label-key="label"
            class="w-full"
            placeholder="Choisir…"
          />
        </UFormField>
      </div>
      <UFormField
        label="N° de certification (optionnel)"
        description="eBay : 30 caractères max. Précisez aussi la note dans le titre ou la description si besoin."
      >
        <UInput
          v-model="gradedCertNumber"
          class="w-full max-w-md"
          maxlength="30"
        />
      </UFormField>
      <UAlert
        color="info"
        variant="subtle"
        icon="i-lucide-info"
        title="Places de marché"
      >
        <template #description>
          <p class="text-sm leading-relaxed">
            <strong>Vinted</strong> utilisera l’état « Neuf avec étiquette » pour une carte sous slab.
            <strong>eBay</strong> enverra la condition « Gradée par un professionnel » avec la société et la note choisies.
          </p>
        </template>
      </UAlert>
    </div>
    <UFormField label="Description" required>
      <UTextarea v-model="description" :rows="4" class="w-full" />
    </UFormField>
    <div class="grid gap-4 sm:grid-cols-3">
      <UFormField label="Pokémon">
        <UInput v-model="pokemonName" class="w-full" />
      </UFormField>
      <UFormField label="Code set">
        <UInput v-model="setCode" class="w-full" />
      </UFormField>
      <UFormField label="Numéro carte">
        <UInput v-model="cardNumber" class="w-full" />
      </UFormField>
    </div>
    <div class="grid gap-4 sm:grid-cols-2">
      <UFormField label="Prix d'achat (€)" required>
        <UInput
          v-model="purchasePrice"
          type="text"
          inputmode="decimal"
          class="w-full"
        />
      </UFormField>
      <UFormField label="Prix de vente (€)">
        <UInput
          v-model="sellPrice"
          type="text"
          inputmode="decimal"
          class="w-full"
          :placeholder="mode === 'create' ? 'Optionnel — utilisé pour Vinted' : undefined"
        />
      </UFormField>
    </div>

    <UAlert
      v-if="mode === 'create' && !hideVintedOption && !importIsSold && isDesktopApp && svcSettings && !svcSettings.vinted_enabled"
      color="warning"
      variant="subtle"
      icon="i-lucide-store"
      title="Vinted désactivé"
    >
      <template #description>
        <p class="text-sm leading-relaxed">
          Réactivez Vinted dans
          <NuxtLink to="/settings/marketplaces" class="font-medium text-primary underline underline-offset-2">
            Paramètres → Places de marché
          </NuxtLink>
          pour proposer la publication automatisée.
        </p>
      </template>
    </UAlert>
    <div
      v-else-if="mode === 'create' && !hideVintedOption && canUseVinted && !importIsSold"
      class="rounded-lg border border-default p-4 space-y-2"
    >
      <UCheckbox
        v-model="publishToVinted"
        label="Publier sur Vinted"
      />
      <p class="text-sm text-muted">
        Si coché, l'API tente de créer l'annonce (identifiants Vinted et automation navigateur requis).
      </p>
    </div>
    <UAlert
      v-else-if="mode === 'create' && !hideVintedOption && !importIsSold"
      color="info"
      variant="subtle"
      icon="i-lucide-sparkles"
      title="Publication Vinted disponible uniquement dans l'app desktop"
    >
      <template #description>
        <p class="text-sm leading-relaxed">
          Installez la version Windows ou macOS depuis
          <NuxtLink
            to="/downloads"
            class="font-medium text-primary underline decoration-primary/40 underline-offset-2 hover:decoration-primary"
          >
            Télécharger l'app
          </NuxtLink>
          pour activer la case « Publier sur Vinted » (si Vinted est activé dans les paramètres).
        </p>
      </template>
    </UAlert>

    <div
      v-if="mode === 'create' && showEbayPublish"
      class="rounded-lg border border-default p-4 space-y-2"
    >
      <UCheckbox
        v-model="publishToEbay"
        :disabled="!canPublishEbay"
        label="Publier sur eBay"
      />
      <p v-if="canPublishEbay" class="text-sm text-muted">
        Une annonce sera créée sur votre compte eBay France en même temps que l'article. Ajoutez au moins une photo pour la mise en ligne.
      </p>
      <p v-else-if="!svcSettings?.ebay_connected" class="text-sm text-muted">
        Connectez votre compte eBay dans
        <NuxtLink to="/settings/marketplaces" class="text-primary underline underline-offset-2">
          Paramètres → Places de marché
        </NuxtLink>
        pour activer cette option.
      </p>
      <p v-else class="text-sm text-muted">
        Terminez la configuration eBay (adresse d'expédition et règles automatiques) dans
        <NuxtLink to="/settings/marketplaces" class="text-primary underline underline-offset-2">
          Paramètres → Places de marché
        </NuxtLink>.
      </p>
    </div>

    <div v-if="mode === 'create'" class="space-y-2">
      <label class="text-sm font-medium text-highlighted">Images</label>
      <div class="flex flex-wrap gap-2">
        <div
          v-for="(src, i) in previews"
          :key="i"
          class="relative size-24 rounded-lg overflow-hidden ring ring-default"
        >
          <img :src="src" alt="" class="size-full object-cover">
          <UButton
            color="error"
            variant="solid"
            size="xs"
            class="absolute top-1 right-1"
            icon="i-lucide-x"
            @click="removePreview(i)"
          />
        </div>
      </div>
      <UInput
        type="file"
        accept="image/*"
        multiple
        :ui="{
          base: 'w-full cursor-pointer file:cursor-pointer'
        }"
        @change="onFiles"
      />
    </div>

    <div v-if="mode === 'edit' && article?.images?.length" class="space-y-2">
      <p class="text-sm font-medium text-highlighted">
        Images existantes
      </p>
      <div class="flex flex-wrap gap-2">
        <img
          v-for="im in article.images"
          :key="im.id"
          :src="imageSrc(im.image_url)"
          alt=""
          class="size-24 rounded-lg object-cover ring ring-default"
        >
      </div>
    </div>

    <UButton
      v-if="showSubmitButton"
      color="primary"
      :loading="loading"
      @click="submit"
    >
      {{ mode === 'create' ? "Créer l'article" : 'Enregistrer' }}
    </UButton>
    <p
      v-if="showSubmitButton && loading && loadingHint"
      class="text-sm text-muted flex items-center gap-2"
    >
      <UIcon name="i-lucide-loader-2" class="size-4 shrink-0 animate-spin" />
      {{ loadingHint }}
    </p>
  </div>
</template>
