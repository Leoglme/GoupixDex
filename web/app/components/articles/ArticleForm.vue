<script setup lang="ts">
import type { Article, ArticleUpdateBody } from '~/composables/useArticles'
import type { AppSettings } from '~/composables/useSettings'
import type { WardrobeSlotPrefill } from '~/composables/useWardrobeImportPrefill'

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
const purchasePrice = ref('')
const sellPrice = ref('')

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
  importIsSold.value = false
  importSoldAt.value = null
}

async function applyWardrobeSlot(p: WardrobeSlotPrefill) {
  while (previews.value.length) {
    removePreview(0)
  }
  importIsSold.value = p.isSold
  importSoldAt.value = p.soldAt
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

defineExpose({ applyScanPrefill, addImageFiles, buildCreateFormData, applyWardrobeSlot })

function buildCreateFormData(): FormData {
  const fd = new FormData()
  fd.append('title', title.value.trim())
  fd.append('description', description.value)
  fd.append('purchase_price', purchasePrice.value.trim())
  fd.append('condition', condition.value.trim() || 'Near Mint')
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
      <UFormField label="État">
        <USelect
          v-model="condition"
          :items="conditionOptions"
          value-key="value"
          label-key="label"
          class="w-full"
        />
      </UFormField>
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
