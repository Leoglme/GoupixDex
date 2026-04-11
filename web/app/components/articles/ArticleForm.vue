<script setup lang="ts">
import type { Article, ArticleUpdateBody } from '~/composables/useArticles'

const props = defineProps<{
  mode: 'create' | 'edit'
  article?: Article | null
  loading?: boolean
}>()

const emit = defineEmits<{
  submitCreate: [form: FormData]
  submitEdit: [body: ArticleUpdateBody]
}>()

const title = ref('')
const description = ref('')
const pokemonName = ref('')
const setCode = ref('')
const cardNumber = ref('')
const condition = ref('Near Mint')
const purchasePrice = ref('')
const sellPrice = ref('')

const imageFiles = ref<File[]>([])
const previews = ref<string[]>([])

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
    condition.value = a.condition || 'Near Mint'
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

/** Ajoute des fichiers image (ex. même fichier que le scan OCR). */
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
}

defineExpose({ applyScanPrefill, addImageFiles })

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
  return fd
}

const config = useRuntimeConfig()

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
        <UInput v-model="condition" class="w-full" />
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
      <UFormField
        v-if="mode === 'edit'"
        label="Prix de vente (€)"
      >
        <UInput
          v-model="sellPrice"
          type="text"
          inputmode="decimal"
          class="w-full"
        />
      </UFormField>
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
          :src="`${config.public.apiBase}${im.image_url}`"
          alt=""
          class="size-24 rounded-lg object-cover ring ring-default"
        >
      </div>
    </div>

    <UButton
      color="primary"
      :loading="loading"
      @click="submit"
    >
      {{ mode === 'create' ? 'Créer l’article' : 'Enregistrer' }}
    </UButton>
  </div>
</template>
