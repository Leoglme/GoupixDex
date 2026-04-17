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
const setupLoading = ref(false)
const s = ref<Awaited<ReturnType<typeof getSettings>> | null>(null)

const marketplaceOptions = [
  { label: 'eBay France (EBAY_FR)', value: 'EBAY_FR' },
  { label: 'eBay Allemagne (EBAY_DE)', value: 'EBAY_DE' },
  { label: 'eBay UK (EBAY_GB)', value: 'EBAY_GB' },
  { label: 'eBay US (EBAY_US)', value: 'EBAY_US' },
  { label: 'eBay Italie (EBAY_IT)', value: 'EBAY_IT' },
  { label: 'eBay Espagne (EBAY_ES)', value: 'EBAY_ES' }
]

const marketplaceSelectItems = computed(() => {
  const base = [...marketplaceOptions]
  const mid = s.value?.ebay_marketplace_id?.trim()
  if (mid && !base.some(b => b.value === mid)) {
    base.unshift({ label: mid, value: mid })
  }
  return base
})

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

async function save() {
  if (!s.value) {
    return
  }
  saving.value = true
  try {
    s.value = await updateSettings({
      vinted_enabled: s.value.vinted_enabled,
      ebay_enabled: s.value.ebay_enabled,
      ebay_marketplace_id: s.value.ebay_marketplace_id,
      ebay_category_id: s.value.ebay_category_id?.trim() || null,
      ebay_merchant_location_key: s.value.ebay_merchant_location_key?.trim() || null,
      ebay_fulfillment_policy_id: s.value.ebay_fulfillment_policy_id?.trim() || null,
      ebay_payment_policy_id: s.value.ebay_payment_policy_id?.trim() || null,
      ebay_return_policy_id: s.value.ebay_return_policy_id?.trim() || null
    })
    toast.add({ title: 'Enregistré', color: 'success' })
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  } finally {
    saving.value = false
  }
}

async function loadSellerSetup() {
  setupLoading.value = true
  try {
    const { data } = await $api.get<{
      marketplace_id: string
      locations: { merchantLocationKey: string, name?: string }[]
      fulfillment_policies: { fulfillmentPolicyId: string, name?: string }[]
      payment_policies: { paymentPolicyId: string, name?: string }[]
      return_policies: { returnPolicyId: string, name?: string }[]
    }>('/ebay/seller-setup')
    if (!s.value) {
      return
    }
    const one = <T extends { merchantLocationKey?: string, fulfillmentPolicyId?: string, paymentPolicyId?: string, returnPolicyId?: string }>(arr: T[], key: keyof T) =>
      arr.length === 1 ? String(arr[0]![key]) : null
    const loc = one(data.locations, 'merchantLocationKey')
    const fp = one(data.fulfillment_policies, 'fulfillmentPolicyId')
    const pp = one(data.payment_policies, 'paymentPolicyId')
    const rp = one(data.return_policies, 'returnPolicyId')
    if (loc) {
      s.value.ebay_merchant_location_key = loc
    }
    if (fp) {
      s.value.ebay_fulfillment_policy_id = fp
    }
    if (pp) {
      s.value.ebay_payment_policy_id = pp
    }
    if (rp) {
      s.value.ebay_return_policy_id = rp
    }
    const filled = [loc, fp, pp, rp].filter(Boolean).length
    toast.add({
      title: 'Données vendeur eBay chargées',
      description:
        filled === 4
          ? 'Une seule politique / emplacement détecté : champs préremplis. Sinon complétez à la main.'
          : 'Sélectionnez les IDs dans la liste ou copiez-les depuis la réponse API si besoin.',
      color: 'success'
    })
  } catch (e) {
    toast.add({ title: 'Impossible de charger eBay', description: apiErrorMessage(e), color: 'error' })
  } finally {
    setupLoading.value = false
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
          <UCheckbox v-model="s.ebay_enabled" label="eBay activé (Inventory API, compte connecté requis)" />
          <p class="text-sm text-muted">
            Par défaut : Vinted activé, eBay désactivé. Désactiver Vinted masque les options de publication associées dans les formulaires.
          </p>
        </div>
      </UCard>

      <UCard v-if="s.ebay_enabled && s.ebay_oauth_configured">
        <template #header>
          <p class="font-medium text-highlighted">
            Connexion eBay (OAuth)
          </p>
          <p class="text-sm text-muted">
            Environnement API : <strong>{{ s.ebay_environment }}</strong>
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

      <UCard v-if="s.ebay_enabled">
        <template #header>
          <p class="font-medium text-highlighted">
            Paramètres d’annonce eBay
          </p>
          <p class="text-sm text-muted">
            Identifiants de catégorie eBay, emplacement marchand et politiques « Business » (expédition, paiement, retours).
          </p>
        </template>
        <div class="space-y-4">
          <UFormField label="Marketplace eBay">
            <USelect
              v-model="s.ebay_marketplace_id"
              :items="marketplaceSelectItems"
              value-key="value"
              label-key="label"
              class="w-full max-w-md"
            />
          </UFormField>
          <UFormField
            label="ID catégorie eBay"
            hint="Ex. catégorie cartes à l’unité pour votre site (Taxonomy / suggestions eBay)."
          >
            <UInput v-model="s.ebay_category_id" placeholder="ex. 183454" class="w-full max-w-md" />
          </UFormField>
          <UFormField label="Clé emplacement (merchantLocationKey)">
            <UInput v-model="s.ebay_merchant_location_key" class="w-full max-w-md" />
          </UFormField>
          <UFormField label="ID politique d’expédition (fulfillment)">
            <UInput v-model="s.ebay_fulfillment_policy_id" class="w-full max-w-md" />
          </UFormField>
          <UFormField label="ID politique de paiement">
            <UInput v-model="s.ebay_payment_policy_id" class="w-full max-w-md" />
          </UFormField>
          <UFormField label="ID politique de retours">
            <UInput v-model="s.ebay_return_policy_id" class="w-full max-w-md" />
          </UFormField>

          <UBadge
            :color="s.ebay_listing_config_complete ? 'success' : 'warning'"
            variant="subtle"
          >
            {{
              s.ebay_listing_config_complete
                ? 'Configuration annonce complète'
                : 'Il manque des champs pour publier sur eBay'
            }}
          </UBadge>

          <div class="flex flex-wrap gap-2">
            <UButton
              v-if="s.ebay_connected"
              color="neutral"
              variant="soft"
              :loading="setupLoading"
              icon="i-lucide-download"
              @click="loadSellerSetup"
            >
              Importer emplacement & politiques (si unique)
            </UButton>
            <UButton :loading="saving" @click="save">
              Enregistrer
            </UButton>
          </div>
        </div>
      </UCard>

      <UCard v-else>
        <p class="text-sm text-muted">
          Activez eBay ci-dessus pour configurer la connexion OAuth et les politiques d’annonce.
        </p>
        <UButton class="mt-4" :loading="saving" @click="save">
          Enregistrer les canaux
        </UButton>
      </UCard>

    </template>
  </div>
</template>
