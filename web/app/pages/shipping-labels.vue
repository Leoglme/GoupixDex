<script setup lang="ts">
import type { EbayUnshippedOrder, ShippingLabelInput } from '~/composables/useShippingLabels'
import { apiErrorMessage } from '~/composables/useApiError'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  "Étiquettes d'envoi",
  "Génération d'étiquettes A4 (Avery L7173, 8 par feuille) pour vos envois postaux GoupixDex avec le logo et l'adresse de l'acheteur."
)

interface LabelRow extends ShippingLabelInput {
  /** Stable identifier — `ebay:<orderId>` for API rows, `manual:<n>` for hand-typed entries. */
  uid: string
  source: 'ebay' | 'manual'
  ebayOrderId: string | null
}

const { fetchEbayOrders, generateLabelsPdf } = useShippingLabels()
const toast = useToast()

const orders = ref<EbayUnshippedOrder[]>([])
const loadingOrders = ref(false)
const ebayUnavailable = ref(false)

const labels = ref<LabelRow[]>([])
const previewUrl = ref<string | null>(null)
const previewBlob = ref<Blob | null>(null)
const previewLoading = ref(false)
const lastPreviewSignature = ref<string>('')

const manual = reactive<ShippingLabelInput>({
  full_name: '',
  line1: '',
  line2: '',
  postal_code: '',
  city: '',
  state: '',
  country_code: 'FR'
})

const COUNTRY_OPTIONS = [
  { value: 'FR', label: 'France' },
  { value: 'BE', label: 'Belgique' },
  { value: 'LU', label: 'Luxembourg' },
  { value: 'CH', label: 'Suisse' },
  { value: 'DE', label: 'Allemagne' },
  { value: 'AT', label: 'Autriche' },
  { value: 'NL', label: 'Pays-Bas' },
  { value: 'ES', label: 'Espagne' },
  { value: 'PT', label: 'Portugal' },
  { value: 'IT', label: 'Italie' },
  { value: 'IE', label: 'Irlande' },
  { value: 'GB', label: 'Royaume-Uni' },
  { value: 'US', label: 'États-Unis' },
  { value: 'CA', label: 'Canada' },
  { value: 'AU', label: 'Australie' },
  { value: 'JP', label: 'Japon' },
  { value: 'CN', label: 'Chine' },
  { value: 'BR', label: 'Brésil' },
  { value: 'MX', label: 'Mexique' }
] as const

let manualCounter = 0

async function loadOrders() {
  loadingOrders.value = true
  ebayUnavailable.value = false
  try {
    orders.value = await fetchEbayOrders()
  } catch (e: unknown) {
    const status = (e as { response?: { status?: number } })?.response?.status
    if (status === 400) {
      ebayUnavailable.value = true
    } else {
      toast.add({
        title: 'Impossible de charger les commandes eBay',
        description: apiErrorMessage(e),
        color: 'error'
      })
    }
  } finally {
    loadingOrders.value = false
  }
}

const selectedOrderIds = computed(() =>
  new Set(labels.value.filter(l => l.source === 'ebay').map(l => l.ebayOrderId))
)

function isOrderSelected(orderId: string): boolean {
  return selectedOrderIds.value.has(orderId)
}

function toggleOrder(order: EbayUnshippedOrder) {
  const uid = `ebay:${order.order_id}`
  const idx = labels.value.findIndex(l => l.uid === uid)
  if (idx >= 0) {
    labels.value.splice(idx, 1)
    return
  }
  labels.value.push({
    uid,
    source: 'ebay',
    ebayOrderId: order.order_id,
    full_name: order.address.full_name || '',
    line1: order.address.line1 || '',
    line2: order.address.line2 || '',
    postal_code: order.address.postal_code || '',
    city: order.address.city || '',
    state: order.address.state || '',
    country_code: order.address.country_code || 'FR'
  })
}

function addManual() {
  if (!manual.full_name.trim() || !manual.line1.trim() || !manual.city.trim() || !manual.postal_code.trim()) {
    toast.add({
      title: 'Champs incomplets',
      description: 'Nom, adresse, code postal et ville sont requis.',
      color: 'warning'
    })
    return
  }
  manualCounter += 1
  labels.value.push({
    uid: `manual:${manualCounter}`,
    source: 'manual',
    ebayOrderId: null,
    full_name: manual.full_name.trim(),
    line1: manual.line1.trim(),
    line2: manual.line2?.trim() || '',
    postal_code: manual.postal_code.trim(),
    city: manual.city.trim(),
    state: manual.state?.trim() || '',
    country_code: (manual.country_code || 'FR').toUpperCase()
  })
  manual.full_name = ''
  manual.line1 = ''
  manual.line2 = ''
  manual.postal_code = ''
  manual.city = ''
  manual.state = ''
  manual.country_code = 'FR'
}

function removeLabel(uid: string) {
  const idx = labels.value.findIndex(l => l.uid === uid)
  if (idx >= 0) {
    labels.value.splice(idx, 1)
  }
}

function clearAll() {
  labels.value.splice(0, labels.value.length)
}

const labelsPayload = computed<ShippingLabelInput[]>(() =>
  labels.value.map(l => ({
    full_name: l.full_name,
    line1: l.line1,
    line2: l.line2 || null,
    postal_code: l.postal_code,
    city: l.city,
    state: l.state || null,
    country_code: l.country_code || 'FR'
  }))
)

const labelsSignature = computed(() => JSON.stringify(labelsPayload.value))

const previewStale = computed(() =>
  Boolean(previewUrl.value) && labelsSignature.value !== lastPreviewSignature.value
)

function revokePreview() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
  }
  previewUrl.value = null
  previewBlob.value = null
  lastPreviewSignature.value = ''
}

async function refreshPreview() {
  if (labels.value.length === 0) {
    toast.add({
      title: 'Aucune étiquette',
      description: 'Sélectionnez une commande ou ajoutez une étiquette manuelle.',
      color: 'warning'
    })
    return
  }
  previewLoading.value = true
  try {
    const blob = await generateLabelsPdf(labelsPayload.value)
    revokePreview()
    previewBlob.value = blob
    previewUrl.value = URL.createObjectURL(blob)
    lastPreviewSignature.value = labelsSignature.value
  } catch (e) {
    toast.add({
      title: 'Génération du PDF impossible',
      description: apiErrorMessage(e),
      color: 'error'
    })
  } finally {
    previewLoading.value = false
  }
}

function downloadPdf() {
  if (!previewBlob.value) {
    return
  }
  const url = URL.createObjectURL(previewBlob.value)
  const a = document.createElement('a')
  a.href = url
  const stamp = new Date().toISOString().slice(0, 10)
  a.download = `goupixdex-etiquettes-${stamp}.pdf`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

const pageCount = computed(() => Math.max(1, Math.ceil(labels.value.length / 8)))

onMounted(() => {
  loadOrders()
})

onBeforeUnmount(() => {
  revokePreview()
})

function formatOrderDate(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: 'short',
      year: 'numeric'
    })
  } catch {
    return iso
  }
}

function orderSummary(order: EbayUnshippedOrder): string {
  if (!order.items.length) return '—'
  const first = order.items[0]?.title || ''
  const more = order.items.length - 1
  if (more <= 0) return first
  return `${first} +${more}`
}
</script>

<template>
  <UDashboardPanel id="shipping-labels">
    <template #header>
      <UDashboardNavbar title="Étiquettes d'envoi">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <div class="flex items-center gap-2">
            <UButton
              icon="i-lucide-refresh-cw"
              color="neutral"
              variant="ghost"
              :loading="loadingOrders"
              @click="loadOrders"
            />
          </div>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="w-full px-4 sm:px-6 py-6 sm:py-8 space-y-6 max-w-[1400px] mx-auto">

        <UCard :ui="{ body: 'p-4 sm:p-5' }">
          <template #header>
            <div class="flex flex-col gap-1">
              <p class="text-sm font-medium text-highlighted">
                Format Avery L7173 — 99 × 57 mm, 8 étiquettes par feuille A4
              </p>
              <p class="text-xs text-muted">
                Sélectionnez vos commandes eBay « à expédier » et/ou ajoutez des destinataires à la main, puis générez l'aperçu PDF strictement identique à l'impression.
              </p>
            </div>
          </template>
        </UCard>

        <!-- eBay orders -->
        <UCard :ui="{ body: 'p-0' }">
          <template #header>
            <div class="flex items-center justify-between gap-3">
              <div>
                <p class="text-sm font-medium text-highlighted">
                  Commandes eBay à expédier
                </p>
                <p class="text-xs text-muted">
                  Statuts <code>NOT_STARTED</code> et <code>IN_PROGRESS</code> sur les 90 derniers jours.
                </p>
              </div>
              <UBadge v-if="!loadingOrders" color="neutral" variant="subtle">
                {{ orders.length }} commande{{ orders.length > 1 ? 's' : '' }}
              </UBadge>
            </div>
          </template>

          <div v-if="ebayUnavailable" class="p-5">
            <UAlert
              color="warning"
              icon="i-lucide-link-2-off"
              title="eBay non connecté"
              description="Connectez votre compte eBay dans les Paramètres pour récupérer vos commandes à expédier. Pensez à reconnecter votre compte si vous voyez une erreur de scope (sell.fulfillment a été ajouté)."
            >
              <template #actions>
                <UButton to="/settings/marketplaces" size="xs" color="neutral" variant="subtle">
                  Ouvrir les paramètres
                </UButton>
              </template>
            </UAlert>
          </div>

          <div v-else-if="loadingOrders" class="flex justify-center py-10">
            <UIcon name="i-lucide-loader-2" class="size-6 animate-spin text-primary" />
          </div>

          <div v-else-if="orders.length === 0" class="p-5 text-sm text-muted">
            Aucune commande eBay en attente d'expédition. Vous pouvez quand même créer des étiquettes manuelles ci-dessous.
          </div>

          <div v-else class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="text-xs text-muted uppercase tracking-wide bg-elevated/60">
                <tr>
                  <th class="text-left px-4 py-2 w-10" />
                  <th class="text-left px-3 py-2">
                    Acheteur
                  </th>
                  <th class="text-left px-3 py-2">
                    Adresse
                  </th>
                  <th class="text-left px-3 py-2">
                    Article(s)
                  </th>
                  <th class="text-left px-3 py-2 whitespace-nowrap">
                    Date
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="order in orders"
                  :key="order.order_id"
                  class="border-t border-default hover:bg-elevated/40 cursor-pointer"
                  @click="toggleOrder(order)"
                >
                  <td class="px-4 py-3 align-top">
                    <UCheckbox
                      :model-value="isOrderSelected(order.order_id)"
                      @update:model-value="toggleOrder(order)"
                      @click.stop
                    />
                  </td>
                  <td class="px-3 py-3 align-top">
                    <p class="font-medium text-highlighted">
                      {{ order.address.full_name || '—' }}
                    </p>
                    <p v-if="order.buyer_username" class="text-xs text-muted">
                      @{{ order.buyer_username }}
                    </p>
                  </td>
                  <td class="px-3 py-3 align-top text-muted">
                    <div class="leading-snug">
                      <p>{{ order.address.line1 }}</p>
                      <p v-if="order.address.line2">
                        {{ order.address.line2 }}
                      </p>
                      <p>
                        {{ order.address.postal_code }} {{ order.address.city }}
                        <span v-if="order.address.country_code && order.address.country_code !== 'FR'" class="ml-1 text-xs uppercase">
                          · {{ order.address.country_code }}
                        </span>
                      </p>
                    </div>
                  </td>
                  <td class="px-3 py-3 align-top text-muted">
                    {{ orderSummary(order) }}
                  </td>
                  <td class="px-3 py-3 align-top text-muted whitespace-nowrap">
                    {{ formatOrderDate(order.creation_date) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </UCard>

        <!-- Manual entry -->
        <UCard :ui="{ body: 'p-4 sm:p-5' }">
          <template #header>
            <p class="text-sm font-medium text-highlighted">
              Ajouter une étiquette manuelle
            </p>
            <p class="text-xs text-muted">
              Pratique pour un envoi non lié à une vente eBay. N'affecte pas vos commandes.
            </p>
          </template>

          <div class="grid gap-3 sm:grid-cols-2">
            <UFormField label="Nom complet" required>
              <UInput v-model="manual.full_name" placeholder="John Doe" class="w-full" />
            </UFormField>
            <UFormField label="Adresse (ligne 1)" required>
              <UInput v-model="manual.line1" placeholder="13 rue Paul Martin" class="w-full" />
            </UFormField>
            <UFormField label="Complément (bât., étage, app.)">
              <UInput v-model="manual.line2" placeholder="BAT B ÉTAGE 1" class="w-full" />
            </UFormField>
            <div class="grid grid-cols-2 gap-3">
              <UFormField label="Code postal" required>
                <UInput v-model="manual.postal_code" placeholder="35000" class="w-full" />
              </UFormField>
              <UFormField label="Ville" required>
                <UInput v-model="manual.city" placeholder="Rennes" class="w-full" />
              </UFormField>
            </div>
            <UFormField label="Région / État (US/CA uniquement)">
              <UInput v-model="manual.state" placeholder="NY" class="w-full" />
            </UFormField>
            <UFormField label="Pays">
              <USelect
                v-model="manual.country_code"
                :items="COUNTRY_OPTIONS"
                value-key="value"
                class="w-full"
              />
            </UFormField>
          </div>

          <template #footer>
            <div class="flex justify-end">
              <UButton icon="i-lucide-plus" @click="addManual">
                Ajouter à la planche
              </UButton>
            </div>
          </template>
        </UCard>

        <!-- Selected labels -->
        <UCard :ui="{ body: 'p-0' }">
          <template #header>
            <div class="flex items-center justify-between gap-3 flex-wrap">
              <div>
                <p class="text-sm font-medium text-highlighted">
                  Étiquettes à imprimer
                </p>
                <p class="text-xs text-muted">
                  {{ labels.length }} étiquette{{ labels.length > 1 ? 's' : '' }}
                  · {{ pageCount }} page{{ pageCount > 1 ? 's' : '' }} A4 (8 par feuille).
                  Modifications éphémères : la commande eBay d'origine n'est pas modifiée.
                </p>
              </div>
              <div class="flex items-center gap-2">
                <UButton
                  v-if="labels.length > 0"
                  size="xs"
                  color="neutral"
                  variant="ghost"
                  icon="i-lucide-trash-2"
                  @click="clearAll"
                >
                  Tout vider
                </UButton>
              </div>
            </div>
          </template>

          <div v-if="labels.length === 0" class="p-5 text-sm text-muted">
            Aucune étiquette sélectionnée pour le moment.
          </div>

          <div v-else class="divide-y divide-default">
            <div
              v-for="label in labels"
              :key="label.uid"
              class="p-4 sm:p-5 grid gap-3 lg:grid-cols-[auto_1fr_auto] items-start"
            >
              <UBadge
                :color="label.source === 'ebay' ? 'warning' : 'neutral'"
                variant="subtle"
                class="shrink-0"
              >
                {{ label.source === 'ebay' ? `eBay #${label.ebayOrderId?.slice(-6)}` : 'Manuel' }}
              </UBadge>
              <div class="grid gap-2 sm:grid-cols-2">
                <UInput v-model="label.full_name" placeholder="Nom complet" />
                <UInput v-model="label.line1" placeholder="Adresse" />
                <UInput v-model="label.line2" placeholder="Complément" />
                <div class="grid grid-cols-[1fr_2fr] gap-2">
                  <UInput v-model="label.postal_code" placeholder="CP" />
                  <UInput v-model="label.city" placeholder="Ville" />
                </div>
                <UInput v-model="label.state" placeholder="État (US/CA)" />
                <USelect
                  v-model="label.country_code"
                  :items="COUNTRY_OPTIONS"
                  value-key="value"
                />
              </div>
              <UButton
                color="neutral"
                variant="ghost"
                icon="i-lucide-x"
                size="sm"
                @click="removeLabel(label.uid)"
              />
            </div>
          </div>

          <template #footer>
            <div class="flex flex-wrap items-center justify-between gap-3">
              <p v-if="previewStale" class="text-xs text-warning">
                <UIcon name="i-lucide-alert-circle" class="inline-block mr-1 size-3.5" />
                L'aperçu n'est plus à jour, régénérez-le.
              </p>
              <span v-else />
              <div class="flex items-center gap-2">
                <UButton
                  icon="i-lucide-eye"
                  :loading="previewLoading"
                  :disabled="labels.length === 0"
                  @click="refreshPreview"
                >
                  Générer l'aperçu
                </UButton>
                <UButton
                  icon="i-lucide-download"
                  color="primary"
                  :disabled="!previewBlob || previewStale"
                  @click="downloadPdf"
                >
                  Télécharger le PDF
                </UButton>
              </div>
            </div>
          </template>
        </UCard>

        <!-- PDF preview -->
        <UCard v-if="previewUrl" :ui="{ body: 'p-0' }">
          <template #header>
            <p class="text-sm font-medium text-highlighted">
              Aperçu PDF (rendu identique à l'impression)
            </p>
          </template>
          <iframe
            :src="previewUrl"
            class="w-full h-[80vh] bg-elevated/40"
            title="Aperçu de la planche d'étiquettes"
          />
        </UCard>

      </div>
    </template>
  </UDashboardPanel>
</template>
