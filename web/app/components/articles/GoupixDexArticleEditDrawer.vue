<template>
  <GoupixDexAppDrawer
    :open="props.open"
    title="Modifier l’article"
    :subtitle="drawerSubtitle"
    icon="i-lucide-square-pen"
    @close="saveThenClose"
  >
    <div v-if="isLoadingArticle" class="flex justify-center py-12">
      <UIcon name="i-lucide-loader-circle" class="size-8 animate-spin text-(--app-accent)" />
    </div>

    <div v-else-if="article" class="space-y-5">
      <GoupixDexArticlePricingGuide
        :set-code="article.set_code ?? ''"
        :card-number="article.card_number ?? ''"
        :pokemon-name="article.pokemon_name ?? ''"
        :purchase-price="parseEuroAmount(purchasePriceText)"
        :cached-cardmarket-eur="article.market_cardmarket_eur ?? null"
        :cached-tcgplayer-eur="article.market_tcgplayer_eur ?? null"
        :order-context="article.order_context ?? null"
        @apply-suggested="applySuggestedSellPrice"
      />

      <section class="space-y-2">
        <div class="grid grid-cols-2 gap-3">
          <UFormField label="Prix de vente (€)">
            <UInput
              v-model="sellPriceText"
              type="text"
              inputmode="decimal"
              placeholder="—"
              class="w-full"
              @blur="saveChangedFields"
              @keydown.enter="leaveField"
            />
          </UFormField>
          <UFormField label="Prix d'achat (€)">
            <UInput
              v-model="purchasePriceText"
              type="text"
              inputmode="decimal"
              class="w-full"
              @blur="saveChangedFields"
              @keydown.enter="leaveField"
            />
          </UFormField>
        </div>
        <p v-if="onlineListingsHint" class="text-muted text-xs leading-relaxed">{{ onlineListingsHint }}</p>
      </section>

      <UFormField label="Titre" :hint="titleLengthLabel">
        <UInput
          v-model="titleDraft"
          class="w-full"
          :maxlength="VINTED_TITLE_MAX_CHARS"
          @blur="saveChangedFields"
          @keydown.enter="leaveField"
        />
      </UFormField>

      <UFormField label="Description">
        <UTextarea v-model="descriptionDraft" :rows="6" autoresize class="w-full" @blur="saveChangedFields" />
      </UFormField>
    </div>
  </GoupixDexAppDrawer>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType, Ref } from 'vue'
import type { Article, ArticleUpdateBody } from '~/composables/useArticles'
import type { ArticleFieldChanges, GoupixDexArticleEditDrawerProps } from '~/types/GoupixDexArticleEditDrawer'
import type { Marketplace } from '~/types/Marketplace'
import { MARKETPLACES, isPublishedOnMarketplace, marketplaceNamesLabel } from '~/utils/marketplaces'
import { parseEuroAmount } from '~/utils/sealedProducts'
import { titleWithinVintedUppercaseRunRule } from '~/utils/vintedTitle'

const props: GoupixDexArticleEditDrawerProps = defineProps({
  open: {
    type: Boolean,
    default: false,
  },
  articleId: {
    type: Number as PropType<number | null>,
    default: null,
  },
})

const emit = defineEmits<{
  close: []
  updated: [article: Article]
}>()

const VINTED_TITLE_MAX_CHARS: number = 100

const toast = useToast()
const { getArticle, updateArticle } = useArticles()

const article: Ref<Article | null> = ref(null)
const isLoadingArticle: Ref<boolean> = ref(false)
const sellPriceText: Ref<string> = ref('')
const purchasePriceText: Ref<string> = ref('')
const titleDraft: Ref<string> = ref('')
const descriptionDraft: Ref<string> = ref('')

let pendingSaves: Promise<boolean> = Promise.resolve(true)

const drawerSubtitle: ComputedRef<string | undefined> = computed((): string | undefined =>
  article.value ? `#${article.value.id} · ${article.value.pokemon_name || article.value.title}` : undefined,
)

const onlineListingsHint: ComputedRef<string | null> = computed((): string | null => {
  const loadedArticle: Article | null = article.value
  if (!loadedArticle) {
    return null
  }
  const onlineMarketplaces: Marketplace[] = MARKETPLACES.filter((marketplace: Marketplace): boolean =>
    isPublishedOnMarketplace(loadedArticle, marketplace),
  )
  return onlineMarketplaces.length
    ? `Déjà en ligne sur ${marketplaceNamesLabel(onlineMarketplaces)} : ces annonces gardent leur prix et leur texte.`
    : null
})

const titleLengthLabel: ComputedRef<string> = computed(
  (): string => `${titleDraft.value.trim().length} / ${VINTED_TITLE_MAX_CHARS}`,
)

/**
 * Écrit un prix dans un champ comme on le tape au clavier français (« 2,40 »).
 * @param {number | null} price - Prix en euros, `null` quand il n'y en a pas.
 * @returns {string} Texte du champ, vide sans prix.
 */
function formatPriceDraft(price: number | null): string {
  return price != null ? price.toFixed(2).replace('.', ',') : ''
}

/**
 * Charge l'article et recopie ses valeurs dans les champs.
 * @param {number} articleId - Article à modifier.
 * @returns {Promise<void>} Résolue quand les champs sont remplis, ou l'échec affiché.
 */
async function loadArticle(articleId: number): Promise<void> {
  isLoadingArticle.value = true
  article.value = null
  try {
    const loadedArticle: Article = await getArticle(articleId)
    article.value = loadedArticle
    sellPriceText.value = formatPriceDraft(loadedArticle.sell_price)
    purchasePriceText.value = formatPriceDraft(loadedArticle.purchase_price)
    titleDraft.value = loadedArticle.title
    descriptionDraft.value = loadedArticle.description
  } catch (error: unknown) {
    toast.add({ title: 'Article introuvable', description: apiErrorMessage(error), color: 'error' })
  } finally {
    isLoadingArticle.value = false
  }
}

/**
 * Relève les champs modifiés et valides ; un champ invalide est signalé et laissé de côté.
 * @param {Article} savedArticle - Article tel qu'enregistré.
 * @returns {ArticleFieldChanges} Champs à enregistrer (vide quand rien n'a changé) et présence d'un champ invalide.
 */
function collectFieldChanges(savedArticle: Article): ArticleFieldChanges {
  const changedFields: ArticleUpdateBody = {}
  let hasInvalidField: boolean = false

  const sellPrice: number | null = parseEuroAmount(sellPriceText.value)
  if (sellPriceText.value.trim() && sellPrice === null) {
    hasInvalidField = true
    toast.add({
      title: 'Prix de vente invalide',
      description: 'Indiquez un montant, par exemple 2,40.',
      color: 'error',
    })
  } else if (sellPrice !== savedArticle.sell_price) {
    changedFields.sell_price = sellPrice
  }

  const purchasePrice: number | null = parseEuroAmount(purchasePriceText.value)
  if (purchasePrice === null) {
    hasInvalidField = true
    toast.add({ title: 'Prix d’achat invalide', description: 'Indiquez un montant, par exemple 0,50.', color: 'error' })
  } else if (purchasePrice !== savedArticle.purchase_price) {
    changedFields.purchase_price = purchasePrice
  }

  const title: string = titleDraft.value.trim()
  if (title !== savedArticle.title) {
    if (!title) {
      hasInvalidField = true
      toast.add({ title: 'Titre requis', description: 'Indiquez un titre pour l’article.', color: 'error' })
    } else if (!titleWithinVintedUppercaseRunRule(title)) {
      hasInvalidField = true
      toast.add({
        title: 'Titre Vinted',
        description: 'Vinted refuse plus de 3 lettres majuscules de suite : ajoutez un espace ou des minuscules.',
        color: 'error',
      })
    } else {
      changedFields.title = title
    }
  }

  if (descriptionDraft.value !== savedArticle.description) {
    changedFields.description = descriptionDraft.value
  }
  return { changedFields, hasInvalidField }
}

/**
 * Enregistre tout de suite les champs modifiés et valides de l'article.
 * @returns {Promise<boolean>} Vrai quand tout est enregistré (ou que rien n'avait changé), faux si un champ reste à corriger.
 */
async function saveChangedFieldsNow(): Promise<boolean> {
  const savedArticle: Article | null = article.value
  if (!savedArticle) {
    return true
  }
  const { changedFields, hasInvalidField }: ArticleFieldChanges = collectFieldChanges(savedArticle)
  if (!Object.keys(changedFields).length) {
    return !hasInvalidField
  }
  try {
    const updatedArticle: Article = await updateArticle(savedArticle.id, changedFields)
    article.value = updatedArticle
    emit('updated', updatedArticle)
    toast.add({ title: 'Article mis à jour', color: 'success' })
    return !hasInvalidField
  } catch (error: unknown) {
    toast.add({ title: 'Mise à jour impossible', description: apiErrorMessage(error), color: 'error' })
    return false
  }
}

/**
 * Enregistre les champs modifiés après les enregistrements déjà lancés, quand un champ est quitté.
 * @returns {Promise<boolean>} Vrai quand tout est enregistré (ou que rien n'avait changé).
 */
function saveChangedFields(): Promise<boolean> {
  pendingSaves = pendingSaves.then(saveChangedFieldsNow)
  return pendingSaves
}

/**
 * Reprend le prix conseillé comme prix de vente, puis l'enregistre.
 * @param {number} suggestedPrice - Prix conseillé en euros.
 * @returns {Promise<void>} Résolue après l'enregistrement.
 */
async function applySuggestedSellPrice(suggestedPrice: number): Promise<void> {
  sellPriceText.value = formatPriceDraft(suggestedPrice)
  await saveChangedFields()
}

/**
 * Quitte le champ sur Entrée, ce qui l'enregistre.
 * @param {KeyboardEvent} event - Appui sur Entrée dans le champ.
 * @returns {void}
 */
function leaveField(event: KeyboardEvent): void {
  if (event.target instanceof HTMLElement) {
    event.target.blur()
  }
}

/**
 * Enregistre ce qui a changé puis ferme le panneau ; il reste ouvert si un champ n'a pas pu être enregistré.
 * @returns {Promise<void>} Résolue une fois le panneau fermé, ou l'échec affiché.
 */
async function saveThenClose(): Promise<void> {
  if (await saveChangedFields()) {
    emit('close')
  }
}

watch(
  (): [boolean, number | null] => [props.open, props.articleId],
  ([isOpen, articleId]: [boolean, number | null]): void => {
    if (isOpen && articleId !== null) {
      loadArticle(articleId)
    }
  },
  { immediate: true },
)
</script>
