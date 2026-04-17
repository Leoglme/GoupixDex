<script setup lang="ts">
definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Paramètres — marketplace',
  'Gérez vos marketplaces de vente et choisissez où publier vos annonces.'
)

const { getSettings, updateSettings } = useSettings()
const { $api } = useNuxtApp()
const toast = useToast()
const route = useRoute()
const router = useRouter()

const loading = ref(true)
const saving = ref(false)
const onboardingLoading = ref(false)
const s = ref<Awaited<ReturnType<typeof getSettings>> | null>(null)

const locationName = ref('Domicile')
/** E.164 (ex. +33642193812), alimenté par le composant PhoneInput. */
const phone = ref('')

const addressLine1 = ref('')
const addressLine2 = ref('')
const city = ref('')
const postalCode = ref('')

async function load() {
  loading.value = true
  try {
    s.value = await getSettings()
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  } finally {
    loading.value = false
  }
}

async function saveChannels() {
  if (!s.value) {
    return
  }
  saving.value = true
  try {
    s.value = await updateSettings({
      vinted_enabled: s.value.vinted_enabled,
      ebay_enabled: s.value.ebay_enabled
    })
    toast.add({ title: 'Enregistré', color: 'success' })
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  } finally {
    saving.value = false
  }
}

async function exchangeOAuthCode(code: string) {
  try {
    await $api.post('/ebay/oauth/exchange', { code })
    toast.add({ title: 'Compte eBay connecté', color: 'success' })
    await load()
  } catch (e) {
    toast.add({ title: 'Échange OAuth échoué', description: apiErrorMessage(e), color: 'error' })
  }
}

async function disconnectEbay() {
  try {
    await $api.post('/ebay/oauth/disconnect')
    toast.add({ title: 'eBay déconnecté', color: 'success' })
    await load()
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  }
}

async function startEbayOAuth() {
  const state = crypto.randomUUID()
  if (import.meta.client) {
    sessionStorage.setItem('ebay_oauth_state', state)
  }
  try {
    const { data } = await $api.get<{ authorization_url: string }>('/ebay/oauth/authorize-url', {
      params: { state }
    })
    if (import.meta.client) {
      window.location.href = data.authorization_url
    }
  } catch (e) {
    toast.add({ title: 'OAuth indisponible', description: apiErrorMessage(e), color: 'error' })
  }
}

async function submitOnboarding() {
  if (!phone.value.trim() || !addressLine1.value.trim() || !city.value.trim() || !postalCode.value.trim()) {
    toast.add({
      title: 'Champs requis',
      description: phone.value.trim()
        ? 'Renseignez l’adresse et le code postal.'
        : 'Indiquez un numéro de téléphone mobile valide (avec indicatif pays).',
      color: 'warning'
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
      country: 'FR'
    })
    toast.add({
      title: 'Réglages eBay prêts',
      description: 'Vous pouvez publier vos cartes sur eBay France.',
      color: 'success'
    })
    await load()
  } catch (e) {
    toast.add({ title: 'Configuration eBay', description: apiErrorMessage(e), color: 'error' })
  } finally {
    onboardingLoading.value = false
  }
}

onMounted(async () => {
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
    await router.replace({ path: '/settings/marketplaces', query: {} })
  }
  await load()
})
</script>

<template>
  <div class="max-w-3xl space-y-6">
    <div>
      <UButton to="/settings" color="neutral" variant="ghost" icon="i-lucide-arrow-left">
        Retour
      </UButton>
    </div>
    <div class="space-y-2">
      <div>
        <h1 class="text-lg font-semibold text-highlighted">
          Marketplace
        </h1>
        <p class="text-sm text-muted">
          Activez ou désactivez Vinted et eBay pour choisir où publier vos annonces.
        </p>
      </div>
    </div>

    <UAlert
      v-if="!loading && s && !s.ebay_oauth_configured"
      color="warning"
      variant="subtle"
      title="Connexion eBay indisponible pour le moment"
      description="La connexion eBay n'est pas encore active sur cette instance."
    />

    <div v-if="loading || !s" class="text-muted text-sm py-8">
      Chargement…
    </div>

    <template v-else>
      <UCard>
        <template #header>
          <p class="font-medium text-highlighted">
            Canaux
          </p>
        </template>
        <div class="space-y-4">
          <UCheckbox v-model="s.vinted_enabled" label="Vinted activé (publication depuis l’app desktop)" />
          <UCheckbox v-model="s.ebay_enabled" label="eBay activé (France — compte connecté requis)" />
          <p class="text-sm text-muted">
            eBay est configuré pour <strong>eBay France</strong> uniquement (cartes Pokémon, envoi depuis votre adresse).
          </p>
          <UButton :loading="saving" @click="saveChannels">
            Enregistrer les canaux
          </UButton>
        </div>
      </UCard>

      <UCard v-if="s.ebay_enabled && s.ebay_oauth_configured">
        <template #header>
          <p class="font-medium text-highlighted">
            eBay France
          </p>
          <p class="text-sm text-muted">
            Environnement : <strong>{{ s.ebay_environment }}</strong>
          </p>
        </template>
        <div class="flex flex-wrap gap-2 items-center">
          <UBadge :color="s.ebay_connected ? 'success' : 'neutral'" variant="subtle">
            {{ s.ebay_connected ? 'Connecté' : 'Non connecté' }}
          </UBadge>
          <UButton
            v-if="!s.ebay_connected"
            icon="i-lucide-link"
            @click="startEbayOAuth"
          >
            Se connecter à eBay
          </UButton>
          <UButton
            v-else
            color="neutral"
            variant="soft"
            icon="i-lucide-unlink"
            @click="disconnectEbay"
          >
            Déconnecter
          </UButton>
        </div>
      </UCard>

      <UCard
        v-if="s.ebay_enabled && s.ebay_connected && s.ebay_listing_config_complete"
        class="border-success/30"
      >
        <p class="font-medium text-highlighted">
          Prêt pour eBay
        </p>
        <p class="text-sm text-muted mt-1">
          Vos annonces peuvent être publiées sur eBay France depuis les formulaires d’articles.
        </p>
      </UCard>

      <UCard v-if="s.ebay_enabled && s.ebay_connected && !s.ebay_listing_config_complete">
        <template #header>
          <p class="font-medium text-highlighted">
            Terminer la configuration (2 minutes)
          </p>
        </template>

        <div class="space-y-6">
          <div class="space-y-3 text-sm text-muted">
            <p class="font-medium text-highlighted">
              Étape 1 — Connexion
            </p>
            <p>Vous êtes connecté à eBay. Nous utilisons votre compte uniquement pour publier vos cartes.</p>

            <p class="font-medium text-highlighted pt-2">
              Étape 2 — Adresse d’expédition
            </p>
            <p>
              Indiquez l’adresse d’où vous postez vos colis. Nous créons automatiquement l’emplacement et les règles eBay
              (livraison France, paiement, retours) sans que vous alliez sur le site eBay.
            </p>
          </div>

          <div class="grid gap-4 sm:grid-cols-2">
            <UFormField label="Nom du lieu (ex. Domicile)">
              <UInput v-model="locationName" class="w-full" />
            </UFormField>
            <UFormField
              label="Téléphone mobile"
              required
              class="min-w-0 sm:col-span-2"
              description="Indicatif pays + numéro. Le clavier numérique s’ouvre sur mobile."
            >
              <PhoneInput v-model="phone" name="phone" default-country-code="FR" class="w-full" />
            </UFormField>
            <UFormField label="Adresse ligne 1" class="sm:col-span-2" required>
              <UInput v-model="addressLine1" class="w-full" />
            </UFormField>
            <UFormField label="Adresse ligne 2 (optionnel)" class="sm:col-span-2">
              <UInput v-model="addressLine2" class="w-full" />
            </UFormField>
            <UFormField label="Ville" required>
              <UInput v-model="city" class="w-full" />
            </UFormField>
            <UFormField label="Code postal" required>
              <UInput v-model="postalCode" class="w-full" />
            </UFormField>
            <UFormField label="Pays">
              <p class="text-sm text-muted py-2">
                France (FR)
              </p>
            </UFormField>
          </div>

          <p v-if="s.ebay_category_id?.trim()" class="text-xs text-muted">
            Catégorie personnalisée (compte) : {{ s.ebay_category_id }}
          </p>
          <p v-else class="text-xs text-muted">
            Catégorie par défaut (eBay France, application) : {{ s.ebay_default_category_id }}
          </p>

          <UButton
            :loading="onboardingLoading"
            icon="i-lucide-wand-sparkles"
            @click="submitOnboarding"
          >
            Créer mes réglages eBay automatiquement
          </UButton>
        </div>
      </UCard>

      <UCard v-else-if="s.ebay_enabled && !s.ebay_connected">
        <p class="text-sm text-muted">
          Connectez votre compte eBay ci-dessus pour lancer l’assistant.
        </p>
      </UCard>

      <UCard v-else-if="!s.ebay_enabled">
        <p class="text-sm text-muted">
          Activez eBay dans « Canaux » pour configurer la vente sur eBay France.
        </p>
      </UCard>
    </template>
  </div>
</template>
