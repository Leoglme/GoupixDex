<template>
  <div class="app-dashboard-page w-full space-y-10">
    <div class="space-y-3 sm:space-y-4">
      <GoupixDexBackLink to="/dashboard" />
      <GoupixDexPageHeader
        title="Paramètres"
        description="Marge sur les prix suggérés, canaux de vente et comptes marketplace — tout au même endroit."
      />
    </div>

    <UAlert
      v-if="!loading && s && !s.ebay_oauth_configured"
      color="warning"
      variant="subtle"
      icon="i-lucide-info"
      title="Connexion eBay indisponible"
      description="La connexion eBay n'est pas encore active sur cette instance."
    />

    <div v-if="loading || !s" class="text-muted py-10 text-center text-sm">Chargement des paramètres…</div>

    <template v-else>
      <!-- ——— Prix ——— -->
      <section class="space-y-4" aria-labelledby="settings-pricing-heading">
        <header class="space-y-1">
          <p id="settings-pricing-heading" class="app-label !text-[0.62rem]">Prix</p>
          <h2 class="text-highlighted text-base font-semibold">Tarification</h2>
          <p class="text-muted max-w-2xl text-sm leading-relaxed">
            La marge s’applique au prix suggéré lors du scan, du lookup Cardmarket et des fiches article.
          </p>
        </header>

        <GoupixDexCollapsibleCard
          v-model:open="openMargin"
          title="Marge de revente"
          description="Pourcentage ajouté au prix catalogue pour proposer un prix de vente."
          body-ui="p-4 sm:p-5"
        >
          <UFormField label="Marge (%)" hint="Valeur habituelle : 15 à 30 %">
            <UInput v-model.number="margin" type="number" min="0" max="500" class="w-full max-w-xs" />
          </UFormField>
          <template #footer>
            <div class="flex justify-end border-t border-[var(--app-line)] pt-4">
              <UButton :loading="savingMargin" icon="i-lucide-save" @click="saveMargin"> Enregistrer la marge </UButton>
            </div>
          </template>
        </GoupixDexCollapsibleCard>
      </section>

      <!-- ——— Ventes ——— -->
      <section class="space-y-4" aria-labelledby="settings-sales-heading">
        <header class="space-y-1">
          <p id="settings-sales-heading" class="app-label !text-[0.62rem]">Ventes</p>
          <h2 class="text-highlighted text-base font-semibold">Places de marché</h2>
          <p class="text-muted max-w-2xl text-sm leading-relaxed">
            Activez les canaux où vous publiez, puis configurez chaque compte. Vinted et Leboncoin passent par
            l’application desktop.
          </p>
        </header>

        <div class="space-y-3">
          <GoupixDexCollapsibleCard
            v-model:open="openChannels"
            title="Canaux actifs"
            description="Vinted, eBay France et Leboncoin — sans activation, la publication est masquée dans les formulaires."
            body-ui="p-4 sm:p-5 space-y-4"
          >
            <UCheckbox v-model="s.vinted_enabled" label="Vinted (publication via l’app desktop)" />
            <UCheckbox v-model="s.ebay_enabled" label="eBay France (OAuth + adresse d’expédition)" />
            <UCheckbox v-model="s.leboncoin_enabled" label="Leboncoin (publication via l’app desktop)" />
            <p class="text-muted text-xs leading-relaxed">
              eBay est limité à <strong>eBay France</strong> (cartes Pokémon, expédition depuis votre adresse).
            </p>
            <div class="flex justify-end pt-1">
              <UButton :loading="savingChannels" icon="i-lucide-save" @click="saveChannels">
                Enregistrer les canaux
              </UButton>
            </div>
          </GoupixDexCollapsibleCard>

          <GoupixDexCollapsibleCard
            v-if="s.vinted_enabled"
            v-model:open="openVinted"
            title="Compte Vinted"
            description="Identifiants chiffrés — utilisés par le worker local pour publier vos annonces."
            body-ui="p-0"
          >
            <template #trailing>
              <UBadge :color="vintedLinked ? 'success' : 'neutral'" variant="subtle" class="hidden sm:inline-flex">
                {{ vintedLinked ? 'Lié' : 'Non lié' }}
              </UBadge>
            </template>
            <GoupixDexVintedAccountCard embedded />
          </GoupixDexCollapsibleCard>

          <GoupixDexCollapsibleCard
            v-if="s.leboncoin_enabled"
            v-model:open="openLeboncoin"
            title="Session Leboncoin"
            description="Profil Chromium local — connectez-vous une fois sur leboncoin.fr."
            body-ui="p-0"
          >
            <template #trailing>
              <UBadge :color="leboncoinBadge.color" variant="subtle" class="hidden sm:inline-flex">
                {{ leboncoinBadge.label }}
              </UBadge>
            </template>
            <GoupixDexLeboncoinSessionCard
              :enabled="s.leboncoin_enabled"
              embedded
              @update:session="onLeboncoinSessionUpdate"
            />
          </GoupixDexCollapsibleCard>

          <GoupixDexCollapsibleCard
            v-if="s.ebay_enabled && s.ebay_oauth_configured"
            v-model:open="openEbay"
            title="eBay France"
            :description="ebayCollapsibleDescription"
            body-ui="p-4 sm:p-5 space-y-6"
          >
            <template #trailing>
              <UBadge :color="ebayBadgeColor" variant="subtle" class="hidden sm:inline-flex">
                {{ ebayBadgeLabel }}
              </UBadge>
            </template>

            <div class="flex flex-wrap items-center gap-2">
              <UBadge :color="s.ebay_connected ? 'success' : 'neutral'" variant="subtle">
                {{ s.ebay_connected ? 'Compte connecté' : 'Non connecté' }}
              </UBadge>
              <span class="text-muted text-xs">Environnement {{ s.ebay_environment }}</span>
            </div>
            <div class="flex flex-wrap gap-2">
              <UButton v-if="!s.ebay_connected" icon="i-lucide-link" @click="startEbayOAuth">
                Se connecter à eBay
              </UButton>
              <UButton v-else color="neutral" variant="soft" icon="i-lucide-unlink" @click="disconnectEbay">
                Déconnecter
              </UButton>
            </div>

            <UAlert
              v-if="s.ebay_connected && s.ebay_listing_config_complete"
              color="success"
              variant="subtle"
              icon="i-lucide-check-circle"
              title="Prêt pour eBay"
              description="Vous pouvez publier vos cartes depuis les fiches article."
            />

            <div
              v-else-if="s.ebay_connected && !s.ebay_listing_config_complete"
              class="space-y-4 border-t border-[var(--app-line)] pt-4"
            >
              <div class="text-muted space-y-2 text-sm">
                <p class="text-highlighted font-medium">Adresse d’expédition</p>
                <p>
                  Indiquez d’où vous expédiez. GoupixDex crée l’emplacement et les règles eBay (livraison France,
                  paiement, retours).
                </p>
              </div>
              <div class="grid gap-4 sm:grid-cols-2">
                <UFormField label="Nom du lieu">
                  <UInput v-model="locationName" class="w-full" />
                </UFormField>
                <UFormField
                  label="Téléphone mobile"
                  required
                  class="min-w-0 sm:col-span-2"
                  description="Indicatif pays + numéro."
                >
                  <GoupixDexPhoneInput v-model="phone" name="phone" default-country-code="FR" class="w-full" />
                </UFormField>
                <p class="text-muted text-xs leading-snug sm:col-span-2">
                  Même adresse que dans
                  <strong class="text-highlighted font-medium">Mon profil</strong> (menu compte). Les champs ci-dessous
                  sont préremplis depuis votre profil.
                </p>
                <UFormField label="Adresse ligne 1" class="sm:col-span-2" required>
                  <GoupixDexAddressAutocompleteInput
                    v-model="addressLine1"
                    placeholder="Numéro et voie"
                    @select="onEbayAddressSelect"
                  />
                </UFormField>
                <UFormField label="Adresse ligne 2 (optionnel)" class="sm:col-span-2">
                  <UInput v-model="addressLine2" class="w-full" />
                </UFormField>
                <UFormField label="Code postal" required>
                  <GoupixDexPostalCodeAutocompleteInput v-model="postalCode" @select="onEbayPostalCodeSelect" />
                </UFormField>
                <UFormField label="Ville" required>
                  <GoupixDexCityAutocompleteInput v-model="city" />
                </UFormField>
                <UFormField label="Pays">
                  <p class="text-muted py-2 text-sm">France (FR)</p>
                </UFormField>
              </div>
              <p v-if="s.ebay_category_id?.trim()" class="text-muted text-xs">
                Catégorie compte : {{ s.ebay_category_id }}
              </p>
              <p v-else class="text-muted text-xs">Catégorie par défaut : {{ s.ebay_default_category_id }}</p>
              <UButton :loading="onboardingLoading" icon="i-lucide-wand-sparkles" @click="submitOnboarding">
                Créer mes réglages eBay
              </UButton>
            </div>

            <p v-else-if="!s.ebay_connected" class="text-muted text-sm">
              Connectez votre compte eBay pour terminer la configuration.
            </p>
          </GoupixDexCollapsibleCard>

          <p v-else-if="s.ebay_enabled && !s.ebay_oauth_configured" class="text-muted text-sm">
            eBay est activé mais la connexion OAuth n’est pas disponible sur cette instance.
          </p>
        </div>
      </section>

      <!-- ——— Achats & outils ——— -->
      <section class="space-y-4" aria-labelledby="settings-tools-heading">
        <header class="space-y-1">
          <p id="settings-tools-heading" class="app-label !text-[0.62rem]">Achats & catalogues</p>
          <h2 class="text-highlighted text-base font-semibold">Comptes associés</h2>
          <p class="text-muted max-w-2xl text-sm leading-relaxed">
            Cardmarket pour le panier et les commandes ; Amazon pour les invitations produit.
          </p>
        </header>

        <div class="space-y-3">
          <div id="cardmarket-connection" class="scroll-mt-24">
            <GoupixDexCollapsibleCard
              v-model:open="openCardmarket"
              title="Cardmarket (panier & commandes)"
              description="Session Chromium locale — limite les blocages Cloudflare lors des achats."
              body-ui="p-0"
            >
              <GoupixDexCardmarketAccountCard embedded />
            </GoupixDexCollapsibleCard>
          </div>

          <div id="amazon-connection" class="scroll-mt-24">
            <GoupixDexCollapsibleCard
              v-model:open="openAmazon"
              title="Amazon (invitations)"
              description="Gérez les comptes utilisés pour les invitations Amazon."
              body-ui="p-0"
            >
              <GoupixDexAmazonAccountCard embedded />
            </GoupixDexCollapsibleCard>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { ComputedRef, Ref } from 'vue'
import type { AppSettings } from '~/composables/useSettings'
import type { LeboncoinSessionResponse } from '~/composables/useLeboncoinWorker'
import type { AddressSuggestion } from '~/types/AddressAutocompleteInput'
import type { PostalCodeCitySuggestion } from '~/types/PostalCodeAutocompleteInput'
import { leboncoinSessionBadge } from '~/utils/leboncoinConnectionUi'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Paramètres',
  'Marge de revente, Vinted, eBay, Leboncoin, Cardmarket et Amazon — configuration GoupixDex.',
)

const { getSettings, updateSettings } = useSettings()
const { me } = useAuth()
const { $api } = useNuxtApp()
const toast = useToast()
const route = useRoute()
const router = useRouter()

const loading: Ref<boolean> = ref(true)
const savingMargin: Ref<boolean> = ref(false)
const savingChannels: Ref<boolean> = ref(false)
const onboardingLoading: Ref<boolean> = ref(false)
const s: Ref<AppSettings | null> = ref(null)
const margin: Ref<number> = ref(20)

const locationName: Ref<string> = ref('Domicile')
const phone: Ref<string> = ref('')
const addressLine1: Ref<string> = ref('')
const addressLine2: Ref<string> = ref('')
const city: Ref<string> = ref('')
const postalCode: Ref<string> = ref('')

const openMargin: Ref<boolean> = ref(true)
const openChannels: Ref<boolean> = ref(false)
const openVinted: Ref<boolean> = ref(false)
const openLeboncoin: Ref<boolean> = ref(false)
const openEbay: Ref<boolean> = ref(false)
const openCardmarket: Ref<boolean> = ref(false)
const openAmazon: Ref<boolean> = ref(false)

const vintedLinked: ComputedRef<boolean> = computed(() => Boolean(me.value?.vinted_email))

const leboncoinSession: Ref<LeboncoinSessionResponse | null> = ref(null)

const leboncoinBadge = computed(() => leboncoinSessionBadge(leboncoinSession.value))

function onLeboncoinSessionUpdate(next: LeboncoinSessionResponse | null) {
  leboncoinSession.value = next
}

const ebayBadgeLabel: ComputedRef<string> = computed(() => {
  if (!s.value?.ebay_connected) {
    return 'À connecter'
  }
  if (!s.value.ebay_listing_config_complete) {
    return 'Adresse requise'
  }
  return 'Prêt'
})

const ebayBadgeColor = computed(() => {
  if (!s.value?.ebay_connected) {
    return 'neutral' as const
  }
  if (!s.value.ebay_listing_config_complete) {
    return 'warning' as const
  }
  return 'success' as const
})

const ebayCollapsibleDescription: ComputedRef<string> = computed(() => {
  if (!s.value?.ebay_connected) {
    return 'OAuth eBay France — requis pour publier vos annonces.'
  }
  if (!s.value.ebay_listing_config_complete) {
    return 'Connecté — complétez l’adresse d’expédition pour publier.'
  }
  return 'Compte connecté et configuration terminée.'
})

function applyHashSections(): void {
  if (!import.meta.client) {
    return
  }
  const hash = route.hash
  if (hash === '#cardmarket-connection') {
    openCardmarket.value = true
  }
  if (hash === '#amazon-connection') {
    openAmazon.value = true
  }
}

function syncShippingFieldsFromSettings(): void {
  if (!s.value) {
    return
  }
  addressLine1.value = s.value.sender_line1 ?? ''
  addressLine2.value = s.value.sender_line2 ?? ''
  postalCode.value = s.value.sender_postal_code ?? ''
  city.value = s.value.sender_city ?? ''
}

function onEbayAddressSelect(suggestion: AddressSuggestion): void {
  postalCode.value = suggestion.postcode
  city.value = suggestion.city
}

function onEbayPostalCodeSelect(suggestion: PostalCodeCitySuggestion): void {
  city.value = suggestion.nom
}

async function load(): Promise<void> {
  loading.value = true
  try {
    s.value = await getSettings()
    margin.value = s.value.margin_percent ?? 20
    syncShippingFieldsFromSettings()
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  } finally {
    loading.value = false
  }
}

async function saveMargin(): Promise<void> {
  savingMargin.value = true
  try {
    const updated = await updateSettings({ margin_percent: margin.value })
    s.value = updated
    margin.value = updated.margin_percent
    toast.add({ title: 'Marge enregistrée', color: 'success' })
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  } finally {
    savingMargin.value = false
  }
}

async function saveChannels(): Promise<void> {
  if (!s.value) {
    return
  }
  savingChannels.value = true
  try {
    s.value = await updateSettings({
      vinted_enabled: s.value.vinted_enabled,
      ebay_enabled: s.value.ebay_enabled,
      leboncoin_enabled: s.value.leboncoin_enabled,
    })
    toast.add({ title: 'Canaux enregistrés', color: 'success' })
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  } finally {
    savingChannels.value = false
  }
}

async function exchangeOAuthCode(code: string): Promise<void> {
  try {
    const { data } = await $api.post<{
      ok: boolean
      has_fulfillment_scope?: boolean
    }>('/ebay/oauth/exchange', { code })
    if (data.has_fulfillment_scope === false) {
      toast.add({
        title: 'eBay connecté — scope commandes manquant',
        description: 'Activez sell.fulfillment sur developer.ebay.com, révoquez GoupixDex sur eBay, puis reconnectez.',
        color: 'warning',
      })
    } else {
      toast.add({ title: 'Compte eBay connecté', color: 'success' })
    }
    openEbay.value = true
    await load()
  } catch (e) {
    toast.add({ title: 'Échange OAuth échoué', description: apiErrorMessage(e), color: 'error' })
  }
}

async function disconnectEbay(): Promise<void> {
  try {
    await $api.post('/ebay/oauth/disconnect')
    toast.add({ title: 'eBay déconnecté', color: 'success' })
    await load()
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  }
}

async function startEbayOAuth(): Promise<void> {
  const state = crypto.randomUUID()
  if (import.meta.client) {
    sessionStorage.setItem('ebay_oauth_state', state)
  }
  try {
    const { data } = await $api.get<{ authorization_url: string }>('/ebay/oauth/authorize-url', {
      params: { state, force_login: true },
    })
    if (import.meta.client) {
      window.location.href = data.authorization_url
    }
  } catch (e) {
    toast.add({ title: 'OAuth indisponible', description: apiErrorMessage(e), color: 'error' })
  }
}

async function submitOnboarding(): Promise<void> {
  if (!phone.value.trim() || !addressLine1.value.trim() || !city.value.trim() || !postalCode.value.trim()) {
    toast.add({
      title: 'Champs requis',
      description: phone.value.trim()
        ? "Renseignez l'adresse et le code postal."
        : 'Indiquez un numéro de mobile valide (avec indicatif).',
      color: 'warning',
    })
    return
  }
  onboardingLoading.value = true
  try {
    await $api.post('/ebay/onboarding/setup', {
      location_name: locationName.value.trim() || 'Domicile',
      phone: phone.value.trim(),
      address_line1: addressLine1.value.trim(),
      address_line2: addressLine2.value.trim() || null,
      city: city.value.trim(),
      postal_code: postalCode.value.trim(),
      country: 'FR',
    })
    toast.add({
      title: 'Réglages eBay prêts',
      description: 'Vous pouvez publier sur eBay France.',
      color: 'success',
    })
    await load()
  } catch (e) {
    toast.add({ title: 'Configuration eBay', description: apiErrorMessage(e), color: 'error' })
  } finally {
    onboardingLoading.value = false
  }
}

onMounted((): void => {
  void (async (): Promise<void> => {
    const code = typeof route.query.code === 'string' ? route.query.code : null
    const st = typeof route.query.state === 'string' ? route.query.state : null
    if (code && import.meta.client) {
      const expected = sessionStorage.getItem('ebay_oauth_state')
      if (st && expected && st !== expected) {
        toast.add({ title: 'État OAuth invalide', description: 'Réessayez la connexion.', color: 'error' })
      } else {
        await exchangeOAuthCode(code)
      }
      sessionStorage.removeItem('ebay_oauth_state')
      await router.replace({ path: '/settings', query: {} })
    }
    await load()
    applyHashSections()
    if (import.meta.client && route.hash) {
      await nextTick()
      const id = route.hash.replace('#', '')
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  })()
})

watch(
  () => route.hash,
  () => {
    applyHashSections()
  },
)
</script>
