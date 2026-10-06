<template>
  <GoupixDexAppDrawer
    :open="open"
    :title="isBundle ? 'Marquer le lot comme vendu' : 'Marquer comme vendu'"
    :subtitle="drawerSubtitle"
    icon="i-lucide-circle-check"
    @close="close"
  >
    <div class="space-y-5">
      <section class="space-y-2">
        <p class="app-label">Vendu sur</p>
        <div class="grid grid-cols-3 gap-2">
          <button
            v-for="marketplace in MARKETPLACES"
            :key="marketplace"
            type="button"
            class="flex flex-col items-center gap-1.5 rounded-lg border px-2 py-3 text-xs font-medium transition-colors"
            :class="
              saleSource === marketplace
                ? 'text-highlighted border-(--app-accent) bg-(--app-accent-soft)'
                : 'text-muted border-(--app-line) hover:border-(--app-ink-soft)'
            "
            :aria-pressed="saleSource === marketplace"
            @click="saleSource = marketplace"
          >
            <GoupixDexMarketplaceAppIcon :marketplace="marketplace" />
            {{ MARKETPLACE_NAMES[marketplace] }}
          </button>
        </div>
        <p v-if="listingsRemovalHint" class="text-muted text-xs">{{ listingsRemovalHint }}</p>
      </section>

      <UAlert
        v-if="isBundle && bundleListedTotalEur == null"
        color="warning"
        variant="subtle"
        title="Répartition impossible sans montants de référence"
        description="Ajoutez un prix affiché ou un prix d’achat sur chaque fiche pour calculer la remise du lot."
      />

      <div
        v-if="isBundle && bundleListedTotalEur != null"
        class="space-y-1 rounded-md border border-(--app-line) bg-(--app-surface-2)/50 px-3 py-2 text-sm"
      >
        <p>
          Total des prix affichés (annonces)&nbsp;:
          <span class="text-highlighted font-semibold">{{ eurPreview.format(bundleListedTotalEur) }}</span>
        </p>
        <p v-if="bundleDiscountHint" class="text-muted text-xs leading-relaxed">
          {{ bundleDiscountHint }}
        </p>
      </div>

      <section class="space-y-1.5">
        <UFormField :label="isBundle ? 'Prix total du lot (€)' : 'Prix réalisé (€)'">
          <UInput v-model="priceInput" type="text" inputmode="decimal" class="w-full" placeholder="0,00" />
        </UFormField>
        <p class="text-muted text-xs">{{ priceHint }}</p>
        <ul
          v-if="bundlePreviewLines.length"
          class="max-h-44 overflow-y-auto rounded-md border border-(--app-line) px-3 py-2 text-xs"
        >
          <li
            v-for="line in bundlePreviewLines"
            :key="line.id"
            class="flex justify-between gap-3 border-b border-(--app-line)/60 py-1.5 last:border-b-0"
          >
            <span class="text-muted min-w-0 truncate">{{ line.label }}</span>
            <span class="text-highlighted shrink-0 font-medium tabular-nums">{{
              eurPreview.format(line.soldPrice)
            }}</span>
          </li>
        </ul>
      </section>
    </div>

    <template #footer>
      <button type="button" class="dialog-btn-secondary" :disabled="isSaving" @click="close">Annuler</button>
      <button type="button" class="dialog-btn-primary" :disabled="isSaving || saleSource === null" @click="submit">
        <UIcon v-if="isSaving" name="i-lucide-loader-circle" class="size-4 animate-spin" />
        {{ isSaving ? 'Enregistrement…' : 'Enregistrer' }}
      </button>
    </template>
  </GoupixDexAppDrawer>
</template>

<script lang="ts" setup>
import type { ComputedRef, ModelRef, PropType, Ref } from 'vue'
import type { Article } from '~/composables/useArticles'
import type {
  ArticleSaleConfirmation,
  BundleSaleAllocation,
  BundleSalePreviewLine,
  GoupixDexArticleMarkSoldDrawerProps,
} from '~/types/GoupixDexArticleMarkSoldDrawer'
import type { Marketplace } from '~/types/Marketplace'
import { MARKETPLACE_NAMES, MARKETPLACES, isPublishedOnMarketplace, marketplaceNamesLabel } from '~/utils/marketplaces'
import { articleListingWeight, splitTotalByWeights } from '~/utils/splitTotalEqualParts'

const props: GoupixDexArticleMarkSoldDrawerProps = defineProps({
  articles: {
    type: Array as PropType<Article[] | null>,
    default: null,
  },
  isSaving: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits<{
  confirm: [sale: ArticleSaleConfirmation]
}>()

const open: ModelRef<boolean> = defineModel('open', { type: Boolean, default: false })

const toast = useToast()

const saleSource: Ref<Marketplace | null> = ref(null)
const priceInput: Ref<string> = ref('')

const eurPreview: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 2,
})

const soldArticles: ComputedRef<Article[]> = computed((): Article[] => props.articles ?? [])

const isBundle: ComputedRef<boolean> = computed((): boolean => soldArticles.value.length > 1)

const drawerSubtitle: ComputedRef<string> = computed((): string => {
  const [firstArticle]: Article[] = soldArticles.value
  if (isBundle.value || !firstArticle) {
    return `${soldArticles.value.length} articles`
  }
  return firstArticle.pokemon_name || firstArticle.title
})

const marketplacesWithListing: ComputedRef<Marketplace[]> = computed((): Marketplace[] =>
  MARKETPLACES.filter((marketplace: Marketplace): boolean =>
    soldArticles.value.some((article: Article): boolean => isPublishedOnMarketplace(article, marketplace)),
  ),
)

const listingsRemovalHint: ComputedRef<string> = computed((): string => {
  if (saleSource.value === null) {
    return 'Choisissez où la vente a eu lieu : les autres annonces seront retirées.'
  }
  const listingsToRemove: Marketplace[] = marketplacesWithListing.value.filter(
    (marketplace: Marketplace): boolean => marketplace !== saleSource.value,
  )
  if (!listingsToRemove.length) {
    return ''
  }
  return `Les annonces ${marketplaceNamesLabel(listingsToRemove)} encore en ligne seront retirées.`
})

const priceHint: ComputedRef<string> = computed((): string =>
  isBundle.value
    ? 'Montant total encaissé pour le lot. Chaque « prix réalisé » suit la même proportion que entre ce total et la somme des prix affichés.'
    : 'Montant réellement encaissé pour cette carte (souvent le prix affiché sur l’annonce si pas de négociation).',
)

const bundleListedTotalEur: ComputedRef<number | null> = computed((): number | null => {
  if (!isBundle.value) {
    return null
  }
  const listedTotal: number = soldArticles.value.reduce(
    (total: number, article: Article): number => total + articleListingWeight(article),
    0,
  )
  const roundedListedTotal: number = Math.round(listedTotal * 100) / 100
  return roundedListedTotal > 0 ? roundedListedTotal : null
})

const enteredPrice: ComputedRef<number | null> = computed((): number | null => {
  const price: number = Number(priceInput.value.replace(',', '.').trim())
  return priceInput.value.trim() === '' || Number.isNaN(price) || price < 0 ? null : price
})

const bundleDiscountHint: ComputedRef<string> = computed((): string => {
  if (bundleListedTotalEur.value == null || enteredPrice.value == null) {
    return ''
  }
  const priceRatio: number = enteredPrice.value / bundleListedTotalEur.value
  return `Équivalent à environ ${formatPercent((1 - priceRatio) * 100)} de remise sur le total des annonces (chaque ligne × ${formatPercent(priceRatio * 100)} du prix pris en compte pour la répartition).`
})

const bundlePreviewLines: ComputedRef<BundleSalePreviewLine[]> = computed((): BundleSalePreviewLine[] => {
  if (!isBundle.value || bundleListedTotalEur.value == null || enteredPrice.value == null) {
    return []
  }
  const splitPrices: number[] = splitTotalByWeights(
    enteredPrice.value,
    soldArticles.value.map((article: Article): number => articleListingWeight(article)),
  )
  return soldArticles.value.map(
    (article: Article, index: number): BundleSalePreviewLine => ({
      id: article.id,
      label: (article.pokemon_name || article.title || '').trim() || `Article ${article.id}`,
      soldPrice: splitPrices[index] ?? 0,
    }),
  )
})

/**
 * Pourcentage à une décimale, virgule française.
 * @param {number} value - Valeur en pourcents.
 * @returns {string} Le pourcentage formaté (« 12,5 % »).
 */
function formatPercent(value: number): string {
  return `${value.toFixed(1).replace('.', ',')} %`
}

/**
 * Canal présélectionné : la seule marketplace où les articles sont en ligne, sinon aucun (choix obligatoire).
 * @returns {Marketplace | null} Le canal évident, ou null.
 */
function findObviousSaleSource(): Marketplace | null {
  const [onlyMarketplace, ...otherMarketplaces]: Marketplace[] = marketplacesWithListing.value
  return onlyMarketplace && !otherMarketplaces.length ? onlyMarketplace : null
}

/**
 * Ferme le drawer sans enregistrer.
 * @returns {void}
 */
function close(): void {
  open.value = false
}

/**
 * Valide le canal et le montant, puis émet la vente unitaire ou la répartition du lot.
 * @returns {void}
 */
function submit(): void {
  if (saleSource.value === null || !soldArticles.value.length) {
    return
  }
  if (enteredPrice.value == null) {
    toast.add({ title: 'Montant invalide', description: 'Indiquez un prix en euros (≥ 0).', color: 'error' })
    return
  }
  if (!isBundle.value) {
    emit('confirm', { mode: 'single', soldPrice: enteredPrice.value, saleSource: saleSource.value })
    return
  }
  if (bundleListedTotalEur.value == null) {
    toast.add({
      title: 'Répartition impossible',
      description:
        'Chaque article doit avoir un prix affiché ou un prix d’achat renseigné pour calculer la remise sur le lot.',
      color: 'error',
    })
    return
  }
  const splitPrices: number[] = splitTotalByWeights(
    enteredPrice.value,
    soldArticles.value.map((article: Article): number => articleListingWeight(article)),
  )
  const allocations: BundleSaleAllocation[] = soldArticles.value.map(
    (article: Article, index: number): BundleSaleAllocation => ({ id: article.id, soldPrice: splitPrices[index] ?? 0 }),
  )
  emit('confirm', { mode: 'bundle', saleSource: saleSource.value, allocations })
}

watch(
  (): boolean => open.value,
  (isOpen: boolean): void => {
    if (isOpen) {
      saleSource.value = findObviousSaleSource()
      priceInput.value = ''
    }
  },
)
</script>
