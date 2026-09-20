<template>
  <div class="space-y-6">
    <div class="grid gap-4 sm:grid-cols-2 sm:items-start">
      <div class="min-w-0 space-y-1.5">
        <UFormField label="Titre" required>
          <UInput v-model="title" class="w-full" :maxlength="mode === 'create' ? VINTED_TITLE_MAX_CHARS : undefined" />
        </UFormField>
        <p class="text-muted text-xs leading-snug">
          {{ titleFieldDescription }}
        </p>
        <p v-if="vintedTitleUppercaseRunInvalid" class="text-xs leading-snug text-red-600 dark:text-red-400">
          Vinted : pas plus de 3 majuscules d’affilée dans le titre. Ex. « Vstar » plutôt que « VSTAR ».
        </p>
      </div>
      <UFormField v-if="!isGraded" label="État" class="min-w-0">
        <USelect v-model="condition" :items="conditionOptions" value-key="value" label-key="label" class="w-full" />
      </UFormField>
    </div>
    <UCheckbox v-model="isGraded" label="Carte gradée (slab — PSA, CGC, BGS…)" class="mt-1" />
    <div v-if="isGraded" class="border-default space-y-4 rounded-lg border p-4">
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
        <UInput v-model="gradedCertNumber" class="w-full max-w-md" maxlength="30" />
      </UFormField>
      <UAlert color="info" variant="subtle" icon="i-lucide-info" title="Places de marché">
        <template #description>
          <p class="text-sm leading-relaxed">
            <strong>Vinted</strong> utilisera l’état « Neuf avec étiquette » pour une carte sous slab.
            <strong>eBay</strong> enverra la condition « Gradée par un professionnel » avec la société et la note
            choisies.
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

    <UCard
      v-if="mode === 'create'"
      class="ring-default border-primary/15 from-primary/5 bg-elevated/40 ring-1"
      :ui="{ body: 'p-4 sm:p-5 space-y-3' }"
    >
      <div class="flex items-center justify-between gap-2">
        <p class="text-highlighted text-sm font-medium">Achats Cardmarket</p>
        <div class="flex items-center gap-2">
          <UIcon
            v-if="orderMatchLoading || linkableLoading"
            name="i-lucide-loader-2"
            class="text-primary size-5 shrink-0 animate-spin"
          />
          <UButton
            color="neutral"
            variant="ghost"
            size="xs"
            icon="i-lucide-refresh-cw"
            :loading="linkableLoading"
            aria-label="Actualiser les lignes d’achat"
            @click="loadLinkableOrderLines"
          />
        </div>
      </div>
      <p v-if="!orderMatchLoading && orderMatchCandidates.length" class="text-muted text-xs leading-relaxed">
        Correspondance automatique : {{ orderMatchCandidates.length }} ligne(s). La plus ancienne avec stock (FIFO) est
        sélectionnée par défaut ; le prix d’achat vient de votre achat le plus récent parmi ces lignes.
      </p>
      <p
        v-else-if="!orderMatchLoading && !linkableLoading && linkableLines.length"
        class="text-muted text-xs leading-relaxed"
      >
        Aucune ligne ne correspond exactement à la carte — choisissez manuellement une ligne d’achat ci-dessous.
      </p>
      <p
        v-else-if="!orderMatchLoading && !linkableLoading && !linkableLines.length"
        class="text-muted text-xs leading-relaxed"
      >
        Aucune ligne d’achat avec stock disponible. Importez une commande Cardmarket ou libérez du stock sur une ligne
        existante.
      </p>
      <UFormField label="Lier à une ligne d’achat">
        <USelect
          v-model="selectedOrderLineIdStr"
          :items="orderLineSelectItems"
          value-key="value"
          label-key="label"
          class="w-full"
          placeholder="Choisir une ligne…"
          :disabled="linkableLoading && !linkableLines.length"
        />
      </UFormField>
      <div v-if="orderMatchCandidates.length" class="space-y-1.5">
        <p class="text-muted text-xs font-medium uppercase">Correspondances auto (date · prix)</p>
        <ul class="text-muted max-h-32 space-y-1 overflow-y-auto text-xs">
          <li v-for="c in orderMatchCandidates" :key="c.order_line_id" class="flex justify-between gap-2 tabular-nums">
            <span>{{ formatOrderMatchRow(c) }}</span>
          </li>
        </ul>
      </div>
    </UCard>

    <GoupixDexArticlePricingGuide
      class="col-span-full"
      :set-code="setCode"
      :card-number="cardNumber"
      :pokemon-name="pokemonName"
      :purchase-price="purchasePriceNumber"
      :cached-cardmarket-eur="article?.market_cardmarket_eur ?? null"
      :cached-tcgplayer-eur="article?.market_tcgplayer_eur ?? null"
      :order-context="article?.order_context ?? null"
      @apply-suggested="onApplySuggestedPrice"
    />

    <div class="grid gap-4 sm:grid-cols-2">
      <UFormField label="Prix d'achat (€)" required>
        <UInput v-model="purchasePrice" type="text" inputmode="decimal" class="w-full" />
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
      v-if="
        mode === 'create' &&
        !hideVintedOption &&
        !importIsSold &&
        isDesktopApp &&
        svcSettings &&
        !svcSettings.vinted_enabled
      "
      color="warning"
      variant="subtle"
      icon="i-lucide-store"
      title="Vinted désactivé"
    >
      <template #description>
        <p class="text-sm leading-relaxed">
          Réactivez Vinted dans
          <NuxtLink to="/settings" class="text-primary font-medium underline underline-offset-2"> Paramètres </NuxtLink>
          pour proposer la publication automatisée.
        </p>
      </template>
    </UAlert>
    <div
      v-else-if="mode === 'create' && !hideVintedOption && canUseVinted && !importIsSold"
      class="border-default space-y-2 rounded-lg border p-4"
    >
      <UCheckbox v-model="publishToVinted" label="Publier sur Vinted" />
      <p class="text-muted text-sm">
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
            class="text-primary decoration-primary/40 hover:decoration-primary font-medium underline underline-offset-2"
          >
            Télécharger l'app
          </NuxtLink>
          pour activer la case « Publier sur Vinted » (si Vinted est activé dans les paramètres).
        </p>
      </template>
    </UAlert>

    <div v-if="mode === 'create' && showEbayPublish" class="border-default space-y-2 rounded-lg border p-4">
      <UCheckbox v-model="publishToEbay" :disabled="!canPublishEbay" label="Publier sur eBay" />
      <p v-if="canPublishEbay" class="text-muted text-sm">
        Une annonce sera créée sur votre compte eBay France en même temps que l'article. Ajoutez au moins une photo pour
        la mise en ligne.
      </p>
      <p v-else-if="!svcSettings?.ebay_connected" class="text-muted text-sm">
        Connectez votre compte eBay dans
        <NuxtLink to="/settings" class="text-primary underline underline-offset-2"> Paramètres </NuxtLink>
        pour activer cette option.
      </p>
      <p v-else class="text-muted text-sm">
        Terminez la configuration eBay (adresse d'expédition et règles automatiques) dans
        <NuxtLink to="/settings" class="text-primary underline underline-offset-2"> Paramètres </NuxtLink>.
      </p>
    </div>

    <div v-if="mode === 'create'" class="space-y-2">
      <label class="text-highlighted text-sm font-medium">Images</label>
      <div class="flex flex-wrap gap-2">
        <div
          v-for="(src, i) in previews"
          :key="i"
          class="ring-default relative size-24 overflow-hidden rounded-lg ring"
        >
          <img :src="src" alt="" class="size-full object-cover" />
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
          base: 'w-full cursor-pointer file:cursor-pointer',
        }"
        @change="onFiles"
      />
    </div>

    <div v-if="mode === 'edit' && article?.images?.length" class="space-y-2">
      <p class="text-highlighted text-sm font-medium">Images existantes</p>
      <div class="flex flex-wrap gap-2">
        <img
          v-for="im in article.images"
          :key="im.id"
          :src="imageSrc(im.image_url)"
          alt=""
          class="ring-default size-24 rounded-lg object-cover ring"
        />
      </div>
    </div>

    <div
      v-if="mode === 'edit' && relistMode && !article?.is_sold"
      class="border-default space-y-3 rounded-lg border border-[var(--app-accent)]/25 bg-[var(--app-accent-soft)]/30 p-4"
    >
      <p class="text-highlighted text-sm font-medium">Republication</p>
      <p class="text-muted text-xs leading-relaxed">
        Enregistrez la fiche puis lancez la mise en ligne sur les canaux cochés (comme à la création).
      </p>
      <UCheckbox
        v-if="canUseVinted"
        v-model="publishToVinted"
        label="Mettre en ligne sur Vinted après enregistrement"
      />
      <UCheckbox
        v-if="showEbayPublish"
        v-model="publishToEbay"
        :disabled="!canPublishEbay"
        label="Mettre en ligne sur eBay après enregistrement"
      />
    </div>

    <div
      v-else-if="
        mode === 'edit' &&
        article &&
        !article.is_sold &&
        !relistMode &&
        ((article.published_on_vinted ?? false) || (article.published_on_ebay ?? false))
      "
      class="border-default space-y-3 rounded-lg border p-4"
    >
      <p class="text-highlighted text-sm font-medium">Statut de publication dans GoupixDex</p>
      <p class="text-muted text-xs leading-relaxed">
        Cochez pour indiquer que l’article n’est plus « en ligne » dans l’app. Cela ne retire pas l’annonce sur Vinted
        ou eBay : supprimez-la sur le site si besoin. Utile pour relancer une publication depuis GoupixDex.
      </p>
      <UCheckbox
        v-if="article.published_on_vinted ?? false"
        v-model="clearVintedPublication"
        label="Ne plus marquer comme publié sur Vinted"
      />
      <UCheckbox
        v-if="article.published_on_ebay ?? false"
        v-model="clearEbayPublication"
        label="Ne plus marquer comme publié sur eBay"
      />
    </div>

    <UButton v-if="showSubmitButton" color="primary" :loading="loading" @click="submit">
      {{ mode === 'create' ? "Créer l'article" : relistMode ? 'Enregistrer et continuer' : 'Enregistrer' }}
    </UButton>
    <p v-if="showSubmitButton && loading && loadingHint" class="text-muted flex items-center gap-2 text-sm">
      <UIcon name="i-lucide-loader-2" class="size-4 shrink-0 animate-spin" />
      {{ loadingHint }}
    </p>
  </div>
</template>

<script setup lang="ts">
import type { ComputedRef, Ref } from 'vue'
import type { Article, ArticleUpdateBody } from '~/composables/useArticles'
import type { AppSettings } from '~/composables/useSettings'
import type { WardrobeSlotPrefill } from '~/composables/useWardrobeImportPrefill'
import type { OrderLinkableLine, OrderMatchResponse } from '~/types/Orders'
import { EBAY_GRADE_OPTIONS, EBAY_PROFESSIONAL_GRADER_OPTIONS } from '~/utils/ebayTradingCardGrading'
import {
  normalizeVintedTitleUppercaseRuns,
  titleWithinVintedUppercaseRunRule as titlePassesVintedUppercaseRule,
} from '~/utils/vintedTitle'

const props = withDefaults(
  defineProps<{
    mode: 'create' | 'edit'
    article?: Article | null
    loading?: boolean
    /** Text shown under the button while loading (e.g. waiting on Vinted). */
    loadingHint?: string | null
    /** Hide the "Publish on Vinted" checkbox (e.g. batch create with a global option). */
    hideVintedOption?: boolean
    /** Mode remise en vente : propose republication après enregistrement. */
    relistMode?: boolean
    /** Show the form submit button (disable if the parent handles submit). */
    showSubmitButton?: boolean
  }>(),
  {
    hideVintedOption: false,
    relistMode: false,
    showSubmitButton: true,
  },
)

export type ArticleEditSubmitOptions = {
  publishVinted: boolean
  publishEbay: boolean
}

const emit = defineEmits<{
  submitCreate: [form: FormData]
  submitEdit: [body: ArticleUpdateBody, relist?: ArticleEditSubmitOptions]
}>()

const VINTED_TITLE_MAX_CHARS: number = 100

const title: Ref<string> = ref('')
const description: Ref<string> = ref('')
const pokemonName: Ref<string> = ref('')
/** OCR variants for Cardmarket match (FR invoice vs EN printed name). */
const ocrPokemonFrench: Ref<string> = ref('')
const ocrPokemonEnglish: Ref<string> = ref('')
const ocrPokemonPrinted: Ref<string> = ref('')
const setCode: Ref<string> = ref('')
const cardNumber: Ref<string> = ref('')
const conditionOptions: { label: string; value: string }[] = [
  { label: 'Mint', value: 'Mint' },
  { label: 'Near Mint', value: 'Near Mint' },
  { label: 'Excellent', value: 'Excellent' },
  { label: 'Good', value: 'Good' },
  { label: 'Played', value: 'Played' },
]

const condition: Ref<string> = ref('Near Mint')
const isGraded: Ref<boolean> = ref(false)
const gradedGraderValueId: Ref<string> = ref('')
const gradedGradeValueId: Ref<string> = ref('')
const gradedCertNumber: Ref<string> = ref('')
const clearVintedPublication: Ref<boolean> = ref(false)
const clearEbayPublication: Ref<boolean> = ref(false)
const purchasePrice: Ref<string> = ref('')
const sellPrice: Ref<string> = ref('')

const purchasePriceNumber = computed((): number | null => {
  const raw = purchasePrice.value.trim().replace(',', '.')
  if (!raw) {
    return null
  }
  const n = Number(raw)
  return Number.isFinite(n) ? n : null
})

function onApplySuggestedPrice(priceEur: number): void {
  sellPrice.value = formatMoneyInput(priceEur)
}
const toast = useToast()
const { matchOrderLines, listLinkableOrderLines } = useOrders()
const orderMatchLoading: Ref<boolean> = ref(false)
const orderMatchCandidates: Ref<OrderMatchResponse['candidates']> = ref([])
const linkableLines: Ref<OrderLinkableLine[]> = ref([])
const linkableLoading: Ref<boolean> = ref(false)
const orderLineTouchedByUser: Ref<boolean> = ref(false)
const selectedOrderLineId: Ref<number | null> = ref(null)
const ocrLanguageCode: Ref<string> = ref('')
let orderMatchDebounce: ReturnType<typeof setTimeout> | null = null

const selectedOrderLineIdStr: ComputedRef<string> = computed({
  get(): string {
    return selectedOrderLineId.value != null ? String(selectedOrderLineId.value) : ''
  },
  set(v: string): void {
    orderLineTouchedByUser.value = true
    selectedOrderLineId.value = v ? Number(v) : null
    void applyPricesFromSelectedLine()
  },
})

const orderLineSelectItems: ComputedRef<{ label: string; value: string }[]> = computed(() => {
  const items: { label: string; value: string }[] = [{ value: '', label: '— Aucune liaison —' }]
  for (const ln of linkableLines.value) {
    items.push({
      value: String(ln.order_line_id),
      label: formatLinkableLineLabel(ln),
    })
  }
  return items
})

const eurFmt: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
})

/**
 * Format a Cardmarket match row for the compact history list.
 * @param c - Candidate row from the API.
 * @returns Single-line summary (locale date + price + order id).
 */
function formatOrderMatchRow(c: OrderMatchResponse['candidates'][number]): string {
  const d = formatShortDate(c.paid_at)
  return `${d} · ${eurFmt.format(c.unit_price_eur)} · commande #${c.external_order_id}`
}

/**
 * Label for manual purchase-line picker options.
 * @param ln - Linkable row from GET /orders/lines/linkable.
 */
function formatLinkableLineLabel(ln: OrderLinkableLine): string {
  const card = [ln.pokemon_label, ln.set_code, ln.card_number].filter(Boolean).join(' · ')
  const state = [ln.language_code, ln.condition_label].filter(Boolean).join('·')
  const bits = [
    `#${ln.external_order_id}`,
    card || '—',
    state,
    eurFmt.format(ln.unit_price_eur),
    `reste ${ln.remaining_units}`,
  ].filter(Boolean)
  return bits.join(' · ')
}

/**
 * Parse ISO-ish date strings for short locale display.
 * @param iso - Nullable API datetime.
 * @returns Human-readable date or em dash.
 */
function formatShortDate(iso: string | null): string {
  if (!iso) {
    return '—'
  }
  try {
    return new Date(iso).toLocaleDateString('fr-FR')
  } catch {
    return '—'
  }
}

/**
 * Recompute purchase and sell price from the selected purchase line and margin settings.
 * @returns {Promise<void>} Nothing.
 */
async function applyPricesFromSelectedLine(): Promise<void> {
  const id = selectedOrderLineId.value
  if (id == null) {
    return
  }
  const row = linkableLines.value.find((x) => x.order_line_id === id)
  if (!row) {
    return
  }
  let margin = 20
  try {
    const s = await getSettings()
    margin = s.margin_percent
  } catch {
    /* keep default */
  }
  const purchase = row.unit_price_eur
  const sell = purchase * (1 + margin / 100)
  purchasePrice.value = formatMoneyInput(purchase)
  sellPrice.value = formatMoneyInput(sell)
}

/**
 * Format a number for price fields (dot decimal — server ``Decimal`` parsing).
 * @param n - Amount in euros.
 * @returns Two-decimal string suitable for ``purchasePrice`` / ``sellPrice``.
 */
function formatMoneyInput(n: number): string {
  return (Math.round(n * 100) / 100).toFixed(2)
}

/**
 * Build pipe-separated Pokémon names for GET /orders/match (FR / EN / printed vs invoice).
 * @returns Combined string for API.
 */
function buildPokemonMatchNameParam(): string {
  const parts = [ocrPokemonFrench.value, ocrPokemonEnglish.value, ocrPokemonPrinted.value, pokemonName.value]
    .map((s) => s.trim())
    .filter(Boolean)
  return [...new Set(parts)].join('|')
}

/**
 * Map OCR language tokens to Cardmarket line codes (JA → JP).
 * @param raw - Raw OCR language code.
 * @returns Normalized code or undefined.
 */
function normalizeLangForOrderMatch(raw: string): string | undefined {
  const u = raw.trim().toUpperCase()
  if (!u) {
    return undefined
  }
  if (u === 'JA' || u === 'JPN') {
    return 'JP'
  }
  return u
}

/**
 * Fetch matching Cardmarket lines and prefill purchase / FIFO link when creating an article.
 * @returns {Promise<void>} Nothing.
 */
/**
 * Load all purchase lines with remaining stock (manual picker).
 */
async function loadLinkableOrderLines(): Promise<void> {
  if (props.mode !== 'create') {
    return
  }
  linkableLoading.value = true
  try {
    linkableLines.value = await listLinkableOrderLines()
    if (selectedOrderLineId.value != null) {
      const still = linkableLines.value.some((x) => x.order_line_id === selectedOrderLineId.value)
      if (!still) {
        selectedOrderLineId.value = null
      }
    }
  } catch {
    linkableLines.value = []
  } finally {
    linkableLoading.value = false
  }
}

async function refreshOrderMatch(): Promise<void> {
  if (props.mode !== 'create') {
    return
  }
  const pk = buildPokemonMatchNameParam()
  const sc = setCode.value.trim()
  const cn = cardNumber.value.trim()
  if (!pk || !sc || !cn) {
    orderMatchCandidates.value = []
    if (!orderLineTouchedByUser.value) {
      selectedOrderLineId.value = null
    }
    return
  }
  orderMatchLoading.value = true
  try {
    const langRaw = ocrLanguageCode.value.trim()
    const lang = langRaw ? (normalizeLangForOrderMatch(langRaw) ?? langRaw) : undefined
    const res = await matchOrderLines({
      pokemon_name: pk,
      set_code: sc,
      card_number: cn,
      condition: condition.value.trim(),
      language_code: lang,
    })
    orderMatchCandidates.value = res.candidates
    if (!orderLineTouchedByUser.value) {
      selectedOrderLineId.value = res.fifo_order_line_id
    }
    if (res.suggested_purchase_price != null && !orderLineTouchedByUser.value) {
      let margin = 20
      try {
        const s = await getSettings()
        margin = s.margin_percent
      } catch {
        /* ignore */
      }
      const purchase = res.suggested_purchase_price
      const sell = purchase * (1 + margin / 100)
      purchasePrice.value = formatMoneyInput(purchase)
      sellPrice.value = formatMoneyInput(sell)
    }
  } catch {
    orderMatchCandidates.value = []
    if (!orderLineTouchedByUser.value) {
      selectedOrderLineId.value = null
    }
  } finally {
    orderMatchLoading.value = false
  }
}

const imageFiles: Ref<File[]> = ref([])
const previews: Ref<string[]> = ref([])
const publishToVinted: Ref<boolean> = ref(false)
const publishToEbay: Ref<boolean> = ref(false)
const svcSettings: Ref<AppSettings | null> = ref(null)
const { getSettings } = useSettings()
const importIsSold: Ref<boolean> = ref(false)
const importSoldAt: Ref<string | null> = ref(null)
const wardrobeVintedListed: Ref<boolean> = ref(false)
const wardrobeVintedPublishedAtIso: Ref<string | null> = ref(null)
const wardrobeImportSoldPrice: Ref<string | null> = ref(null)
const { isDesktopApp } = useDesktopRuntime()
const { fetchBlob: fetchVintedListingImageBlob } = useVintedListingImage()
const canUseVinted = computed(
  () => isDesktopApp.value && !importIsSold.value && svcSettings.value?.vinted_enabled !== false,
)
const showEbayPublish = computed(
  () =>
    !importIsSold.value &&
    svcSettings.value?.ebay_enabled === true &&
    svcSettings.value?.ebay_oauth_configured === true,
)
const canPublishEbay = computed(
  () =>
    showEbayPublish.value &&
    svcSettings.value?.ebay_connected === true &&
    svcSettings.value?.ebay_listing_config_complete === true,
)

const titleLenVinted = computed(() => title.value.trim().length)

/**
 * Whether the title fits Vinted length limits.
 * @returns {boolean} True when within limit
 */
function titleWithinVintedLimit(): boolean {
  return titleLenVinted.value <= VINTED_TITLE_MAX_CHARS
}

const vintedTitleUppercaseRunInvalid = computed(
  () => title.value.trim().length > 0 && !titlePassesVintedUppercaseRule(title.value),
)

/**
 * Assign title from an external source (scan, market, catalog), normalized for Vinted rules.
 * @param raw - Raw title text
 * @returns {void} Nothing
 */
function assignTitleFromExternal(raw: string): void {
  const normalized = normalizeVintedTitleUppercaseRuns(raw.trim())
  title.value = normalized.slice(0, VINTED_TITLE_MAX_CHARS)
}

const titleFieldDescription = computed(() => {
  const n = titleLenVinted.value
  const max = VINTED_TITLE_MAX_CHARS
  const base = `${n} / ${max} caractères (limite Vinted, espaces inclus)`
  return n > max ? `${base} — raccourcissez avant enregistrement` : base
})

onMounted(async () => {
  try {
    svcSettings.value = await getSettings()
  } catch {
    svcSettings.value = null
  }
  if (props.mode === 'create') {
    await loadLinkableOrderLines()
  }
})

watch([pokemonName, setCode, cardNumber, condition, ocrLanguageCode], (): void => {
  if (props.mode !== 'create') {
    return
  }
  if (orderMatchDebounce) {
    clearTimeout(orderMatchDebounce)
  }
  orderMatchDebounce = setTimeout((): void => {
    void refreshOrderMatch()
  }, 450)
})

/**
 * Download listing photo bytes from a URL (browser fetch or desktop helper).
 * @param url - Remote image URL (often Vinted CDN)
 * @returns {Promise<Blob | null>} Blob when fetch succeeds
 */
async function blobFromVintedPhotoUrl(url: string): Promise<Blob | null> {
  try {
    const res = await fetch(url)
    if (res.ok) {
      return await res.blob()
    }
  } catch {
    /* CORS or network */
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
    condition.value = a.condition && conditionOptions.some((o) => o.value === a.condition) ? a.condition : 'Near Mint'
    purchasePrice.value = String(a.purchase_price)
    sellPrice.value = a.sell_price != null ? String(a.sell_price) : ''
    isGraded.value = Boolean(a.is_graded)
    gradedGraderValueId.value =
      a.graded_grader_value_id && EBAY_PROFESSIONAL_GRADER_OPTIONS.some((o) => o.value === a.graded_grader_value_id)
        ? a.graded_grader_value_id
        : ''
    gradedGradeValueId.value =
      a.graded_grade_value_id && EBAY_GRADE_OPTIONS.some((o) => o.value === a.graded_grade_value_id)
        ? a.graded_grade_value_id
        : ''
    gradedCertNumber.value = a.graded_cert_number ?? ''
    clearVintedPublication.value = false
    clearEbayPublication.value = false
    if (props.relistMode && !a.is_sold) {
      publishToVinted.value = Boolean(canUseVinted.value)
      publishToEbay.value = Boolean(canPublishEbay.value)
    }
  },
  { immediate: true },
)

/**
 *
 * @param e
 */
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

/**
 *
 * @param i
 */
function removePreview(i: number) {
  URL.revokeObjectURL(previews.value[i]!)
  previews.value.splice(i, 1)
  imageFiles.value.splice(i, 1)
}

/**
 * Append image files (e.g. same file as OCR scan).
 * @param files
 */
function addImageFiles(files: File[]) {
  for (const f of files) {
    imageFiles.value.push(f)
    previews.value.push(URL.createObjectURL(f))
  }
}

/**
 *
 * @param scan
 * @param scan.listing_preview
 * @param scan.listing_preview.title
 * @param scan.listing_preview.description
 * @param scan.listing_preview.suggested_price
 * @param scan.ocr
 * @param scan.pricing
 * @param scan.pricing.cardmarket_eur
 * @param scan.pricing.tcgplayer_usd
 */
async function applyScanPrefill(scan: {
  listing_preview: { title: string; description: string; suggested_price: number | null }
  ocr: Record<string, unknown>
  pricing: { cardmarket_eur: number | null; tcgplayer_usd: number | null }
}) {
  assignTitleFromExternal(scan.listing_preview.title)
  description.value = scan.listing_preview.description
  const o = scan.ocr
  const nameFr = typeof o.pokemon_name_french === 'string' ? o.pokemon_name_french.trim() : ''
  const nameEn = typeof o.pokemon_name_english === 'string' ? o.pokemon_name_english.trim() : ''
  const printed = typeof o.pokemon_name === 'string' ? o.pokemon_name.trim() : ''
  ocrPokemonFrench.value = nameFr
  ocrPokemonEnglish.value = nameEn
  ocrPokemonPrinted.value = printed
  pokemonName.value = nameEn || nameFr || printed
  setCode.value = typeof o.set_code === 'string' ? o.set_code : ''
  cardNumber.value = typeof o.card_number === 'string' ? o.card_number : ''
  const langRaw = o.language_code ?? o.lang ?? o.language
  ocrLanguageCode.value = typeof langRaw === 'string' ? langRaw : typeof langRaw === 'number' ? String(langRaw) : ''
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
  await refreshOrderMatch()
}

/**
 * Prefill used by the market-search page (``/market``): we only know a subset
 * of the fields (title, price, condition, …) and optionally a remote image URL
 * that we try to fetch as a File so it is bundled with the article creation.
 * @param p
 * @param p.title
 * @param p.description
 * @param p.pokemonName
 * @param p.setCode
 * @param p.cardNumber
 * @param p.condition
 * @param p.purchasePrice
 * @param p.sellPrice
 * @param p.imageUrl
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
  ocrPokemonFrench.value = ''
  ocrPokemonEnglish.value = ''
  ocrPokemonPrinted.value = ''
  if (p.title) {
    assignTitleFromExternal(p.title)
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
  if (p.condition && conditionOptions.some((o) => o.value === p.condition)) {
    condition.value = p.condition
  }
  if (p.purchasePrice) {
    purchasePrice.value = p.purchasePrice
  }
  if (p.sellPrice) {
    sellPrice.value = p.sellPrice
  }
  await refreshOrderMatch()
  if (p.imageUrl) {
    try {
      const blob = await blobFromVintedPhotoUrl(p.imageUrl)
      if (blob) {
        const ext = blob.type.includes('png') ? 'png' : 'jpg'
        const file = new File([blob], `ebay-${Date.now()}.${ext}`, {
          type: blob.type || 'image/jpeg',
        })
        addImageFiles([file])
      }
    } catch {
      /* optional image: ignore if download fails (CORS) */
    }
  }
}

/**
 *
 * @param p
 */
async function applyWardrobeSlot(p: WardrobeSlotPrefill) {
  while (previews.value.length) {
    removePreview(0)
  }
  importIsSold.value = p.isSold
  importSoldAt.value = p.soldAt
  wardrobeVintedListed.value = p.wardrobeVintedListed
  wardrobeVintedPublishedAtIso.value = p.vintedPublishedAtIso
  wardrobeImportSoldPrice.value = p.importSoldPrice
  assignTitleFromExternal(p.title)
  description.value = p.description
  purchasePrice.value = p.purchasePrice || '0'
  sellPrice.value = p.sellPrice
  ocrPokemonFrench.value = ''
  ocrPokemonEnglish.value = ''
  ocrPokemonPrinted.value = ''
  pokemonName.value = p.pokemonName
  setCode.value = p.setCode
  cardNumber.value = p.cardNumber
  condition.value = conditionOptions.some((o) => o.value === p.condition) ? p.condition : 'Near Mint'
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
        type: blob.type || 'image/jpeg',
      })
      addImageFiles([file])
    } catch {
      /* optional image */
    }
  }
  await refreshOrderMatch()
}

/**
 * Prefill the article form from a TCGdex card preview payload
 * (used by ``Ma Collection → Préparer la vente``).
 *
 * Photos are optional: when ``photoUrl`` is provided we try to download the
 * TCGdex HD image and attach it as the first file (best-effort, CORS may fail).
 */
async function applyCatalogPrefill(p: {
  listing_preview: { title: string; description: string; suggested_price: number | null }
  pokewallet: { set_code: string; card_number: string }
  display_pokemon_name?: string
  tcgdex?: { names?: { en?: string | null; fr?: string | null; ja?: string | null } }
  image_url_high?: string | null
  pricing?: {
    cardmarket_eur: number | null
    tcgplayer_usd: number | null
    average_price_eur: number | null
    error: string | null
  }
}) {
  assignTitleFromExternal(p.listing_preview.title)
  description.value = p.listing_preview.description
  const fr = p.tcgdex?.names?.fr?.trim() ?? ''
  const en = p.tcgdex?.names?.en?.trim() ?? ''
  ocrPokemonFrench.value = fr
  ocrPokemonEnglish.value = en
  ocrPokemonPrinted.value = p.display_pokemon_name?.trim() ?? ''
  pokemonName.value = p.display_pokemon_name?.trim() || fr || en
  setCode.value = p.pokewallet.set_code
  cardNumber.value = p.pokewallet.card_number
  if (p.listing_preview.suggested_price != null) {
    sellPrice.value = String(p.listing_preview.suggested_price)
  }
  isGraded.value = false
  gradedGraderValueId.value = ''
  gradedGradeValueId.value = ''
  gradedCertNumber.value = ''
  importIsSold.value = false
  publishToVinted.value = false
  publishToEbay.value = false
  if (p.image_url_high) {
    try {
      const blob = await blobFromVintedPhotoUrl(p.image_url_high)
      if (blob) {
        const ext = blob.type.includes('png') ? 'png' : 'webp'
        const file = new File([blob], `catalog-${Date.now()}.${ext}`, {
          type: blob.type || 'image/webp',
        })
        addImageFiles([file])
      }
    } catch {
      /* image is optional — CORS or HEAD-only servers shouldn't break the form */
    }
  }
  await refreshOrderMatch()
}

defineExpose({
  applyScanPrefill,
  applyCatalogPrefill,
  addImageFiles,
  buildCreateFormData,
  applyWardrobeSlot,
  applyEbayPrefill,
})

/**
 * Build multipart body for article creation API call.
 * @returns {FormData} Payload including fields and image files
 */
function buildCreateFormData(): FormData {
  if (!titleWithinVintedLimit()) {
    throw new Error('ARTICLE_TITLE_TOO_LONG')
  }
  if (!titlePassesVintedUppercaseRule(title.value)) {
    throw new Error('ARTICLE_TITLE_VINTED_UPPERCASE')
  }
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
  if (selectedOrderLineId.value != null) {
    fd.append('order_line_id', String(selectedOrderLineId.value))
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

/**
 * Resolve stored image path or absolute URL for previews.
 * @param url - Relative API path or http(s) URL
 * @returns {string} Absolute URL
 */
function imageSrc(url: string): string {
  if (url.startsWith('http')) {
    return url
  }
  return `${config.public.apiBase}${url}`
}

function submit() {
  if (!title.value.trim()) {
    toast.add({
      title: 'Titre requis',
      description: 'Indiquez un titre pour l’article.',
      color: 'error',
    })
    return
  }
  if (!titleWithinVintedLimit()) {
    toast.add({
      title: 'Titre trop long',
      description: `Vinted : maximum ${VINTED_TITLE_MAX_CHARS} caractères (espaces inclus). Actuellement : ${title.value.trim().length}.`,
      color: 'error',
    })
    return
  }
  if (!titlePassesVintedUppercaseRule(title.value)) {
    toast.add({
      title: 'Titre Vinted',
      description:
        'Vinted refuse plus de 3 lettres majuscules consécutives dans le titre. Ajoutez un espace, un chiffre ou des minuscules pour couper la suite.',
      color: 'error',
    })
    return
  }
  if (isGraded.value) {
    if (!gradedGraderValueId.value || !gradedGradeValueId.value) {
      toast.add({
        title: 'Carte gradée',
        description: 'Choisissez une société de grading et une note (requis pour eBay).',
        color: 'error',
      })
      return
    }
  }
  if (props.mode === 'create') {
    emit('submitCreate', buildCreateFormData())
    return
  }
  const editBody: ArticleUpdateBody = {
    title: title.value.trim(),
    description: description.value,
    pokemon_name: pokemonName.value.trim() || null,
    set_code: setCode.value.trim() || null,
    card_number: cardNumber.value.trim() || null,
    condition: condition.value.trim() || 'Near Mint',
    is_graded: isGraded.value,
    graded_grader_value_id: isGraded.value ? gradedGraderValueId.value : null,
    graded_grade_value_id: isGraded.value ? gradedGradeValueId.value : null,
    graded_cert_number:
      isGraded.value && gradedCertNumber.value.trim() ? gradedCertNumber.value.trim().slice(0, 30) : null,
    purchase_price: Number(purchasePrice.value.replace(',', '.')),
    sell_price: sellPrice.value.trim() ? Number(sellPrice.value.replace(',', '.')) : null,
  }
  if (clearVintedPublication.value) {
    editBody.clear_vinted_publication = true
  }
  if (clearEbayPublication.value) {
    editBody.clear_ebay_publication = true
  }
  if (props.relistMode) {
    emit('submitEdit', editBody, {
      publishVinted: canUseVinted.value && publishToVinted.value,
      publishEbay: canPublishEbay.value && publishToEbay.value,
    })
    return
  }
  emit('submitEdit', editBody)
}
</script>
