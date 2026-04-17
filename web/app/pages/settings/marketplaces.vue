<script setup lang="ts">
definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Paramètres — marketplace',
  'Gérez vos marketplaces de vente et choisissez où publier vos annonces.'
)

type SellerLocation = { merchantLocationKey: string, name?: string }
type FulfillmentRow = { fulfillmentPolicyId: string, name?: string }
type PaymentRow = { paymentPolicyId: string, name?: string }
type ReturnRow = { returnPolicyId: string, name?: string }

const { getSettings, updateSettings } = useSettings()
const { $api } = useNuxtApp()
const toast = useToast()
const route = useRoute()
const router = useRouter()

const loading = ref(true)
const saving = ref(false)
const setupLoading = ref(false)
const s = ref<Awaited<ReturnType<typeof getSettings>> | null>(null)

const sellerLocations = ref<SellerLocation[]>([])
const sellerFulfillment = ref<FulfillmentRow[]>([])
const sellerPayment = ref<PaymentRow[]>([])
const sellerReturns = ref<ReturnRow[]>([])

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

function rowLabel(name: string | undefined, id: string) {
  const n = name?.trim()
  return n ? `${n} — ${id}` : id
}

function withSavedFallback<T extends { label: string, value: string }>(
  items: T[],
  current: string | null | undefined
): T[] {
  const cur = current?.trim()
  if (cur && !items.some(i => i.value === cur)) {
    return [{ label: `${cur} (enregistré)`, value: cur } as T, ...items]
  }
  return items
}

const locationSelectItems = computed(() => {
  const base = sellerLocations.value.map(l => ({
    label: rowLabel(l.name, l.merchantLocationKey),
    value: l.merchantLocationKey
  }))
  return withSavedFallback(base, s.value?.ebay_merchant_location_key)
})

const fulfillmentSelectItems = computed(() => {
  const base = sellerFulfillment.value.map(p => ({
    label: rowLabel(p.name, p.fulfillmentPolicyId),
    value: p.fulfillmentPolicyId
  }))
  return withSavedFallback(base, s.value?.ebay_fulfillment_policy_id)
})

const paymentSelectItems = computed(() => {
  const base = sellerPayment.value.map(p => ({
    label: rowLabel(p.name, p.paymentPolicyId),
    value: p.paymentPolicyId
  }))
  return withSavedFallback(base, s.value?.ebay_payment_policy_id)
})

const returnSelectItems = computed(() => {
  const base = sellerReturns.value.map(p => ({
    label: rowLabel(p.name, p.returnPolicyId),
    value: p.returnPolicyId
  }))
  return withSavedFallback(base, s.value?.ebay_return_policy_id)
})

const categoryHint = computed(() => {
  const d = s.value?.ebay_default_category_id?.trim()
  if (d) {
    return `Laisser vide pour utiliser la catégorie définie sur le serveur (${d}). Sinon, saisissez un autre identifiant.`
  }
  return 'Identifiant de catégorie eBay pour vos annonces. Sinon, une catégorie par défaut peut être configurée côté serveur.'
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

async function loadSellerSetup(opts: { silent?: boolean, fillSingleIfEmpty?: boolean } = {}) {
  const silent = opts.silent ?? false
  const fillSingleIfEmpty = opts.fillSingleIfEmpty ?? true
  if (!s.value?.ebay_connected) {
    sellerLocations.value = []
    sellerFulfillment.value = []
    sellerPayment.value = []
    sellerReturns.value = []
    return
  }
  setupLoading.value = true
  try {
    const mp = s.value.ebay_marketplace_id?.trim() || 'EBAY_FR'
    const { data } = await $api.get<{
      marketplace_id: string
      locations: SellerLocation[]
      fulfillment_policies: FulfillmentRow[]
      payment_policies: PaymentRow[]
      return_policies: ReturnRow[]
    }>('/ebay/seller-setup', { params: { marketplace_id: mp } })

    sellerLocations.value = data.locations ?? []
    sellerFulfillment.value = data.fulfillment_policies ?? []
    sellerPayment.value = data.payment_policies ?? []
    sellerReturns.value = data.return_policies ?? []

    if (!s.value) {
      return
    }

    const one = <T extends Record<string, unknown>>(arr: T[], key: keyof T) =>
      arr.length === 1 ? String(arr[0]![key]) : null

    if (fillSingleIfEmpty) {
      if (!s.value.ebay_merchant_location_key?.trim()) {
        const v = one(sellerLocations.value, 'merchantLocationKey')
        if (v) {
          s.value.ebay_merchant_location_key = v
        }
      }
      if (!s.value.ebay_fulfillment_policy_id?.trim()) {
        const v = one(sellerFulfillment.value, 'fulfillmentPolicyId')
        if (v) {
          s.value.ebay_fulfillment_policy_id = v
        }
      }
      if (!s.value.ebay_payment_policy_id?.trim()) {
        const v = one(sellerPayment.value, 'paymentPolicyId')
        if (v) {
          s.value.ebay_payment_policy_id = v
        }
      }
      if (!s.value.ebay_return_policy_id?.trim()) {
        const v = one(sellerReturns.value, 'returnPolicyId')
        if (v) {
          s.value.ebay_return_policy_id = v
        }
      }
    }

    if (!silent) {
      const nLoc = sellerLocations.value.length
      const nF = sellerFulfillment.value.length
      const nP = sellerPayment.value.length
      const nR = sellerReturns.value.length
      toast.add({
        title: 'Listes eBay chargées',
        description: `${nLoc} emplacement(s), ${nF} expédition, ${nP} paiement, ${nR} retours.`,
        color: 'success'
      })
    }
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
    await loadSellerSetup({ silent: true, fillSingleIfEmpty: true })
  } catch (e) {
    toast.add({ title: 'Échange OAuth échoué', description: apiErrorMessage(e), color: 'error' })
  }
}

async function disconnectEbay() {
  try {
    await $api.post('/ebay/oauth/disconnect')
    toast.add({ title: 'eBay déconnecté', color: 'success' })
    sellerLocations.value = []
    sellerFulfillment.value = []
    sellerPayment.value = []
    sellerReturns.value = []
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
  if (s.value?.ebay_connected) {
    await loadSellerSetup({ silent: true, fillSingleIfEmpty: true })
  }
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
          <UCheckbox v-model="s.ebay_enabled" label="eBay activé (compte connecté requis)" />
          <p class="text-sm text-muted">
            Par défaut : Vinted activé, eBay désactivé. Désactiver Vinted masque les options de publication associées dans les formulaires.
          </p>
        </div>
      </UCard>

      <UCard v-if="s.ebay_enabled && s.ebay_oauth_configured">
        <template #header>
          <p class="font-medium text-highlighted">
            Connexion eBay
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

      <UCard v-if="s.ebay_enabled">
        <template #header>
          <p class="font-medium text-highlighted">
            Annonce eBay
          </p>
          <p class="text-sm text-muted">
            Choisissez le site eBay, la catégorie si besoin, puis l’emplacement et les règles d’expédition, de paiement et de retours (listes issues de votre compte après connexion).
          </p>
        </template>
        <div class="space-y-4">
          <UFormField
            label="Site eBay (marketplace)"
            hint="Après un changement, utilisez « Actualiser les listes » pour recharger emplacement et politiques."
          >
            <USelect
              v-model="s.ebay_marketplace_id"
              :items="marketplaceSelectItems"
              value-key="value"
              label-key="label"
              class="w-full max-w-md"
            />
          </UFormField>

          <UFormField label="Catégorie (optionnel)" :hint="categoryHint">
            <UInput
              v-model="s.ebay_category_id"
              :placeholder="s.ebay_default_category_id?.trim() ? `Défaut serveur : ${s.ebay_default_category_id}` : 'ex. 183454'"
              class="w-full max-w-md"
            />
          </UFormField>

          <UFormField
            label="Emplacement d’expédition"
            :hint="s.ebay_connected ? '' : 'Connectez eBay pour remplir la liste.'"
          >
            <USelect
              v-if="locationSelectItems.length"
              v-model="s.ebay_merchant_location_key"
              :items="locationSelectItems"
              value-key="value"
              label-key="label"
              class="w-full max-w-md"
            />
            <UInput
              v-else
              v-model="s.ebay_merchant_location_key"
              placeholder="Chargement ou saisie manuelle de la clé"
              class="w-full max-w-md"
              :disabled="!s.ebay_connected"
            />
          </UFormField>

          <UFormField label="Expédition">
            <USelect
              v-if="fulfillmentSelectItems.length"
              v-model="s.ebay_fulfillment_policy_id"
              :items="fulfillmentSelectItems"
              value-key="value"
              label-key="label"
              class="w-full max-w-md"
            />
            <UInput
              v-else
              v-model="s.ebay_fulfillment_policy_id"
              placeholder="Identifiant de politique d’expédition"
              class="w-full max-w-md"
              :disabled="!s.ebay_connected"
            />
          </UFormField>

          <UFormField label="Paiement">
            <USelect
              v-if="paymentSelectItems.length"
              v-model="s.ebay_payment_policy_id"
              :items="paymentSelectItems"
              value-key="value"
              label-key="label"
              class="w-full max-w-md"
            />
            <UInput
              v-else
              v-model="s.ebay_payment_policy_id"
              placeholder="Identifiant de politique de paiement"
              class="w-full max-w-md"
              :disabled="!s.ebay_connected"
            />
          </UFormField>

          <UFormField label="Retours">
            <USelect
              v-if="returnSelectItems.length"
              v-model="s.ebay_return_policy_id"
              :items="returnSelectItems"
              value-key="value"
              label-key="label"
              class="w-full max-w-md"
            />
            <UInput
              v-else
              v-model="s.ebay_return_policy_id"
              placeholder="Identifiant de politique de retours"
              class="w-full max-w-md"
              :disabled="!s.ebay_connected"
            />
          </UFormField>

          <UBadge
            :color="s.ebay_listing_config_complete ? 'success' : 'warning'"
            variant="subtle"
          >
            {{
              s.ebay_listing_config_complete
                ? 'Configuration annonce complète'
                : 'Il manque des éléments pour publier sur eBay'
            }}
          </UBadge>

          <div class="flex flex-wrap gap-2">
            <UButton
              v-if="s.ebay_connected"
              color="neutral"
              variant="soft"
              :loading="setupLoading"
              icon="i-lucide-refresh-cw"
              @click="loadSellerSetup({ silent: false, fillSingleIfEmpty: true })"
            >
              Actualiser les listes
            </UButton>
            <UButton :loading="saving" @click="save">
              Enregistrer
            </UButton>
          </div>
        </div>
      </UCard>

      <UCard v-else>
        <p class="text-sm text-muted">
          Activez eBay ci-dessus pour configurer la connexion et l’annonce.
        </p>
        <UButton class="mt-4" :loading="saving" @click="save">
          Enregistrer les canaux
        </UButton>
      </UCard>
    </template>
  </div>
</template>
