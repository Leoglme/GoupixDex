<template>
  <UDashboardPanel id="add-sealed-page">
    <template #header>
      <UDashboardNavbar>
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #title>
          <span class="app-label flex items-center gap-1.5 !text-[0.65rem]">
            <UIcon name="i-lucide-box" class="h-3 w-3 text-(--app-accent)" />
            Ajouter un produit
          </span>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="app-dashboard-page mx-auto w-full max-w-2xl">
        <GoupixDexPageHeader
          title="Ajouter un produit scellé"
          description="Collez un lien Cardmarket pour pré-remplir, ou saisissez les champs à la main."
        >
          <template #actions>
            <UButton color="neutral" variant="ghost" icon="i-lucide-arrow-left" to="/collection/produits">
              Retour
            </UButton>
          </template>
        </GoupixDexPageHeader>

        <UCard :ui="{ body: 'p-4 sm:p-6 space-y-5' }">
          <UFormField
            label="Lien Cardmarket (optionnel)"
            help="Récupère automatiquement le nom, l'image, l'identifiant produit et le prix marché."
          >
            <div class="flex gap-2">
              <UInput
                v-model="cardmarketUrl"
                icon="i-lucide-link"
                placeholder="https://www.cardmarket.com/fr/Pokemon/Products/…"
                class="w-full"
                @keydown.enter.prevent="resolve"
              />
              <UButton
                color="neutral"
                variant="soft"
                icon="i-lucide-wand-2"
                :loading="resolving"
                :disabled="!cardmarketUrl.trim()"
                @click="resolve"
              >
                Récupérer
              </UButton>
            </div>
          </UFormField>

          <div v-if="imageUrl" class="flex justify-center">
            <div class="bg-muted/30 h-40 w-40 overflow-hidden rounded-lg">
              <img
                :src="imageUrl"
                :alt="name || 'Produit'"
                class="h-full w-full object-contain"
                referrerpolicy="no-referrer"
              />
            </div>
          </div>

          <UFormField label="Nom du produit" required>
            <UInput v-model="name" placeholder="ETB Étincelles Déferlantes" class="w-full" />
          </UFormField>

          <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <UFormField label="Type">
              <USelect v-model="productType" :items="typeOptions" value-key="value" label-key="label" class="w-full" />
            </UFormField>
            <UFormField label="Langue">
              <USelect v-model="language" :items="languageItems" value-key="value" label-key="label" class="w-full" />
            </UFormField>
          </div>

          <UFormField label="Set / édition (optionnel)">
            <UInput v-model="setName" placeholder="Écarlate et Violet — Étincelles Déferlantes" class="w-full" />
          </UFormField>

          <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <UFormField label="Quantité">
              <UInput v-model="quantityText" type="number" min="1" step="1" class="w-full" />
            </UFormField>
            <UFormField label="Prix d'achat (€)" help="Base du % de plus-value.">
              <UInput v-model="purchaseText" type="number" min="0" step="0.01" placeholder="—" class="w-full" />
            </UFormField>
            <UFormField label="Prix marché (€)" :help="marketPriceHelp">
              <UInput v-model="marketText" type="number" min="0" step="0.01" placeholder="—" class="w-full" />
            </UFormField>
          </div>

          <UFormField label="Notes (optionnel)">
            <UTextarea v-model="notes" :rows="2" placeholder="État, provenance…" class="w-full" />
          </UFormField>

          <div class="flex items-center justify-end gap-2 pt-1">
            <UButton color="neutral" variant="ghost" to="/collection/produits">Annuler</UButton>
            <UButton color="primary" icon="i-lucide-check" :loading="saving" :disabled="!name.trim()" @click="submit">
              Ajouter à ma collection
            </UButton>
          </div>
        </UCard>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { SealedProductType } from '~/composables/useSealed'
import { SEALED_TYPE_OPTIONS, parseEuroAmount } from '~/utils/sealedProducts'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo('Ajouter un produit scellé', 'Ajoutez un ETB, un coffret ou un display à votre collection GoupixDex.')

const { resolveCardmarket, createSealed } = useSealed()
const toast = useToast()

const typeOptions = SEALED_TYPE_OPTIONS
const languageItems = [
  { label: 'Français', value: 'fr' },
  { label: 'Anglais', value: 'en' },
  { label: 'Japonais', value: 'ja' },
]

const cardmarketUrl = ref('')
const resolving = ref(false)
const saving = ref(false)

const name = ref('')
const productType = ref<SealedProductType>('etb')
const setName = ref('')
const language = ref('fr')
const quantityText = ref('1')
const purchaseText = ref('')
const marketText = ref('')
const imageUrl = ref('')
const cardmarketIdProduct = ref<number | null>(null)

const notes = ref('')

const marketPriceHelp = computed<string>(() =>
  cardmarketIdProduct.value != null
    ? 'Rafraîchi chaque nuit depuis Cardmarket.'
    : 'Saisi manuellement (aucun idProduct).',
)

/**
 * Pré-remplit le formulaire depuis une fiche produit Cardmarket (best-effort).
 * @returns Résolue quand la récupération a abouti ou échoué proprement.
 */
async function resolve(): Promise<void> {
  const url = cardmarketUrl.value.trim()
  if (!url) {
    return
  }
  resolving.value = true
  try {
    const data = await resolveCardmarket(url)
    if (data.name) {
      name.value = data.name
    }
    if (data.image_url) {
      imageUrl.value = data.image_url
    }
    if (data.id_product != null) {
      cardmarketIdProduct.value = data.id_product
    }
    if (data.market_price_eur != null) {
      marketText.value = String(data.market_price_eur)
    }
    if (data.error) {
      toast.add({ title: 'Fiche Cardmarket', description: data.error, color: 'warning' })
    } else {
      toast.add({ title: 'Fiche récupérée', description: 'Vérifiez et complétez les champs.', color: 'success' })
    }
  } catch (e) {
    toast.add({ title: 'Fiche Cardmarket', description: apiErrorMessage(e), color: 'error' })
  } finally {
    resolving.value = false
  }
}

/**
 * Crée le produit scellé puis revient à la liste.
 * @returns Résolue après création (ou en cas d'erreur affichée).
 */
async function submit(): Promise<void> {
  const trimmedName = name.value.trim()
  if (!trimmedName) {
    return
  }
  saving.value = true
  try {
    const quantity = Math.max(1, Math.trunc(Number.parseInt(quantityText.value, 10) || 1))
    await createSealed({
      name: trimmedName,
      product_type: productType.value,
      set_name: setName.value.trim() || null,
      language: language.value,
      quantity,
      purchase_price_eur: parseEuroAmount(purchaseText.value),
      market_price_eur: parseEuroAmount(marketText.value),
      image_url: imageUrl.value.trim() || null,
      cardmarket_id_product: cardmarketIdProduct.value,
      cardmarket_url: cardmarketUrl.value.trim() || null,
      notes: notes.value.trim() || null,
    })
    toast.add({ title: 'Produit ajouté', description: trimmedName, color: 'success' })
    void navigateTo('/collection/produits')
  } catch (e) {
    toast.add({ title: 'Ajout du produit', description: apiErrorMessage(e), color: 'error' })
  } finally {
    saving.value = false
  }
}
</script>
