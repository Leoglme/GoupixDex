<template>
  <UModal v-model:open="open" :title="modalTitle" :description="modalDescription">
    <template #body>
      <div class="space-y-4">
        <UAlert
          v-if="isBundle && articleCount > 0 && bundleListedTotalEur == null"
          color="warning"
          variant="subtle"
          title="Répartition impossible sans montants de référence"
          description="Ajoutez un prix affiché ou un prix d’achat sur chaque fiche pour calculer la remise du lot."
        />

        <UFormField v-if="ebayEnabled" label="Source de la vente">
          <USelect
            v-model="saleSource"
            class="w-full"
            :items="[
              { label: 'Vinted', value: 'vinted' },
              { label: 'eBay', value: 'ebay' },
            ]"
            value-key="value"
            label-key="label"
          />
        </UFormField>
        <p v-else class="text-muted text-sm">
          Vente enregistrée comme <span class="text-highlighted font-medium">Vinted</span>
          (eBay n'est pas activé dans vos paramètres).
        </p>

        <div
          v-if="isBundle && bundleListedTotalEur != null"
          class="border-default bg-elevated/50 space-y-1 rounded-md border px-3 py-2 text-sm"
        >
          <p>
            Total des prix affichés (annonces)&nbsp;:
            <span class="text-highlighted font-semibold">{{ eurPreview.format(bundleListedTotalEur) }}</span>
          </p>
          <p v-if="bundleRemiseHint" class="text-muted text-xs leading-relaxed">
            {{ bundleRemiseHint }}
          </p>
        </div>

        <div class="space-y-1.5">
          <UFormField :label="priceLabel">
            <UInput v-model="priceInput" type="text" inputmode="decimal" class="w-full" placeholder="0,00" />
          </UFormField>
          <p class="text-muted text-xs">{{ priceHint }}</p>
          <ul
            v-if="isBundle && perLinePreview.length"
            class="border-default max-h-44 overflow-y-auto rounded-md border px-3 py-2 text-xs"
          >
            <li
              v-for="row in perLinePreview"
              :key="row.id"
              class="border-default/60 flex justify-between gap-3 border-b py-1.5 last:border-b-0"
            >
              <span class="text-muted min-w-0 truncate">{{ row.label }}</span>
              <span class="text-highlighted shrink-0 font-medium tabular-nums">{{ eurPreview.format(row.sold) }}</span>
            </li>
          </ul>
        </div>

        <div class="flex justify-end gap-2 pt-2">
          <UButton color="neutral" variant="subtle" :disabled="loading" @click="close"> Annuler </UButton>
          <UButton :loading="loading" @click="submit"> Enregistrer </UButton>
        </div>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import type { Ref } from 'vue'
import type { Article } from '~/composables/useArticles'
import { articleListingWeight, splitTotalByWeights } from '~/utils/splitTotalEqualParts'

const props = defineProps<{
  /** One article (vente unitaire) ou plusieurs (lot, répartition selon les prix affichés). */
  articles: Article[] | null
  /** When true, show eBay option; otherwise only Vinted (forced on save). */
  ebayEnabled: boolean
  loading?: boolean
}>()

const open = defineModel<boolean>('open', { default: false })
const toast = useToast()

const emit = defineEmits<{
  confirm: [
    payload:
      | { mode: 'single'; soldPrice: number; saleSource: 'vinted' | 'ebay' }
      | {
          mode: 'bundle'
          saleSource: 'vinted' | 'ebay'
          allocations: { id: number; soldPrice: number }[]
        },
  ]
}>()

const saleSource: Ref<'vinted' | 'ebay'> = ref('vinted')
const priceInput: Ref<string> = ref('')

const articleCount = computed(() => props.articles?.length ?? 0)
const isBundle = computed(() => articleCount.value > 1)

const modalTitle = computed(() => (isBundle.value ? 'Marquer le lot comme vendu' : 'Marquer comme vendu'))

const modalDescription = computed(() =>
  isBundle.value
    ? 'Indiquez le prix total du lot encaissé : la remise est calculée par rapport au total des prix affichés, puis appliquée à chaque article (coefficient identique, ajustement des centimes).'
    : 'Indiquez le canal et le montant réellement encaissé (€).',
)

const priceLabel = computed(() => (isBundle.value ? 'Prix total du lot (€)' : 'Prix réalisé (€)'))

const priceHint = computed(() =>
  isBundle.value
    ? 'Montant total encaissé pour le lot. Chaque « prix réalisé » suit la même proportion que entre ce total et la somme des prix affichés.'
    : 'Montant réellement encaissé pour cette carte (souvent le prix affiché sur l’annonce si pas de négociation).',
)

const eurPreview = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 2,
})

/** Somme des prix affichés (ou prix d’achat en secours) pour le lot. */
const bundleListedTotalEur = computed(() => {
  if (!isBundle.value || !props.articles?.length) {
    return null
  }
  let sum = 0
  for (const a of props.articles) {
    sum += articleListingWeight(a)
  }
  // Évite les résidus flottants (ex. 10.469999…) après somme de décimaux.
  const rounded = Math.round(sum * 100) / 100
  return rounded > 0 ? rounded : null
})

/** Texte remise / coefficient quand le montant négocié est saisi. */
const bundleRemiseHint = computed(() => {
  if (!isBundle.value || bundleListedTotalEur.value == null) {
    return ''
  }
  const listed = bundleListedTotalEur.value
  const raw = priceInput.value.replace(',', '.').trim()
  const n = Number(raw)
  if (Number.isNaN(n) || n < 0) {
    return ''
  }
  const ratio = n / listed
  const remisePct = (1 - ratio) * 100
  const coefPct = ratio * 100
  return `Équivalent à environ ${fmtPct(remisePct)} de remise sur le total des annonces (chaque ligne × ${fmtPct(coefPct)} du prix pris en compte pour la répartition).`
})

function fmtPct(x: number): string {
  const s = x.toFixed(1).replace('.', ',')
  return `${s} %`
}

/** Aperçu ligne à ligne (prix réalisé par carte). */
const perLinePreview = computed(() => {
  if (!isBundle.value || !props.articles?.length || articleCount.value < 2) {
    return [] as { id: number; label: string; sold: number }[]
  }
  const listed = bundleListedTotalEur.value
  if (listed == null || listed <= 0) {
    return []
  }
  const raw = priceInput.value.replace(',', '.').trim()
  const n = Number(raw)
  if (Number.isNaN(n) || n < 0) {
    return []
  }
  const weights = props.articles.map((a) => articleListingWeight(a))
  if (weights.every((w) => w <= 0)) {
    return []
  }
  const splits = splitTotalByWeights(n, weights)
  return props.articles.map((a, i) => ({
    id: a.id,
    label: (a.pokemon_name || a.title || `#${a.id}`).trim() || `Article ${a.id}`,
    sold: splits[i] ?? 0,
  }))
})

watch(
  () => [open.value, props.articles] as const,
  ([isOpen, list]) => {
    if (!isOpen || !list?.length) {
      return
    }
    saleSource.value = 'vinted'
    priceInput.value = ''
  },
)

function close() {
  open.value = false
}

function submit() {
  const list = props.articles
  if (!list?.length) {
    return
  }
  const raw = priceInput.value.replace(',', '.').trim()
  const n = Number(raw)
  if (Number.isNaN(n) || n < 0) {
    toast.add({ title: 'Montant invalide', description: 'Indiquez un prix en euros (≥ 0).', color: 'error' })
    return
  }
  const src = props.ebayEnabled ? saleSource.value : 'vinted'
  if (list.length === 1) {
    emit('confirm', { mode: 'single', soldPrice: n, saleSource: src })
    return
  }
  const weights = list.map((a) => articleListingWeight(a))
  const sumW = weights.reduce((a, b) => a + b, 0)
  if (sumW <= 0) {
    toast.add({
      title: 'Répartition impossible',
      description:
        'Chaque article doit avoir un prix affiché ou un prix d’achat renseigné pour calculer la remise sur le lot.',
      color: 'error',
    })
    return
  }
  const splits = splitTotalByWeights(n, weights)
  const allocations = list.map((a, i) => ({ id: a.id, soldPrice: splits[i]! }))
  emit('confirm', { mode: 'bundle', saleSource: src, allocations })
}
</script>
