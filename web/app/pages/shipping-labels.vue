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
      <div class="mx-auto w-full max-w-[1400px] space-y-6 px-4 py-6 sm:px-6 sm:py-8">
        <UCard :ui="{ body: 'p-4 sm:p-5' }">
          <template #header>
            <div class="flex flex-col gap-1">
              <p class="text-highlighted text-sm font-medium">Destinataires : Avery L7173 — 99 × 57 mm (8 par page)</p>
              <p class="text-muted text-xs">
                Chaque colis : <strong>deux vignettes L7173 distinctes</strong>, l’étiquette expéditeur est placée
                <strong>juste sous</strong> le destinataire (même colonne sur la feuille). Destinataire : vignette
                pleine. Expéditeur : cadre de découpe resserré en hauteur, presque toute la largeur de la vignette ; une
                ligne pour le nom et <strong>une seule ligne</strong> pour l’adresse complète (rue, complément, CP et
                ville). Marges haut et bas égales dans le cadre pour faciliter la découpe. Ordre sur une page : colis A
                destinataire puis expéditeur, colis B dest. puis exp., etc. Une page A4 = jusqu’à 4 colis (8 vignettes).
                Vous pouvez joindre un <strong>PDF timbre</strong> laposte.fr par colis : placé
                <strong>juste sous</strong> la vignette expéditeur lorsque l’emplacement est libre sous cette colonne
                (centré), sinon à <strong>droite</strong> de la feuille, aligné avec la paire destinataire / expéditeur
                du colis — taille PDF identique au fichier La Poste. À l’impression, utilisez
                <strong>taille réelle / 100 %</strong> (pas « ajuster à la page ») pour éviter une réduction visuelle.
                Sinon une page suivante (facultatif). Configurez l’expéditeur dans Paramètres → Configuration.
              </p>
            </div>
          </template>
        </UCard>

        <GoupixDexAlert
          v-if="!senderLoading && !senderAddressComplete"
          variant="warning"
          icon="i-lucide-map-pin"
          title="Adresse expéditeur manquante"
          description="Renseignez votre adresse expéditeur dans Paramètres → Configuration avant de générer le PDF."
        >
          <template #actions>
            <UButton to="/settings" size="xs" color="neutral" variant="subtle"> Ouvrir la configuration </UButton>
          </template>
        </GoupixDexAlert>

        <!-- eBay orders -->
        <UCard :ui="{ body: 'p-0' }">
          <template #header>
            <div class="flex items-center justify-between gap-3">
              <div>
                <p class="text-highlighted text-sm font-medium">Commandes eBay à expédier</p>
                <p class="text-muted text-xs">
                  Statuts <code>NOT_STARTED</code> et <code>IN_PROGRESS</code> sur les 90 derniers jours.
                </p>
              </div>
              <UBadge v-if="!loadingOrders" color="neutral" variant="subtle">
                {{ orders.length }} commande{{ orders.length > 1 ? 's' : '' }}
              </UBadge>
            </div>
          </template>

          <div v-if="ebayUnavailable || ebayScopeMismatch" class="p-5">
            <GoupixDexAlert
              variant="warning"
              :icon="ebayScopeMismatch ? 'i-lucide-shield-alert' : 'i-lucide-link-2-off'"
              :title="ebayScopeMismatch ? 'Autorisation eBay à mettre à jour' : 'eBay non connecté'"
              :description="
                ebayScopeMismatch
                  ? 'Reconnectez votre compte eBay dans les Paramètres pour accorder le scope « sell.fulfillment » (liste des commandes à expédier).'
                  : 'Connectez votre compte eBay dans les Paramètres pour récupérer vos commandes à expédier.'
              "
            >
              <template #actions>
                <UButton to="/settings/marketplaces" size="xs" color="neutral" variant="subtle">
                  {{ ebayScopeMismatch ? 'Reconnecter eBay' : 'Ouvrir les paramètres' }}
                </UButton>
              </template>
            </GoupixDexAlert>
          </div>

          <div v-else-if="loadingOrders" class="flex justify-center py-10">
            <UIcon name="i-lucide-loader-2" class="text-primary size-6 animate-spin" />
          </div>

          <div v-else-if="orders.length === 0" class="text-muted p-5 text-sm">
            Aucune commande eBay en attente d'expédition. Vous pouvez quand même créer des étiquettes manuelles
            ci-dessous.
          </div>

          <div v-else class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="text-muted bg-elevated/60 text-xs tracking-wide uppercase">
                <tr>
                  <th class="w-10 px-4 py-2 text-left" />
                  <th class="px-3 py-2 text-left">Acheteur</th>
                  <th class="px-3 py-2 text-left">Adresse</th>
                  <th class="px-3 py-2 text-left">Article(s)</th>
                  <th class="px-3 py-2 text-left whitespace-nowrap">Date</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="order in orders"
                  :key="order.order_id"
                  class="border-default hover:bg-elevated/40 cursor-pointer border-t"
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
                    <p class="text-highlighted font-medium">
                      {{ order.address.full_name || '—' }}
                    </p>
                    <p v-if="order.buyer_username" class="text-muted text-xs">@{{ order.buyer_username }}</p>
                  </td>
                  <td class="text-muted px-3 py-3 align-top">
                    <div class="leading-snug">
                      <p>{{ order.address.line1 }}</p>
                      <p v-if="order.address.line2">
                        {{ order.address.line2 }}
                      </p>
                      <p>
                        {{ order.address.postal_code }} {{ order.address.city }}
                        <span
                          v-if="order.address.country_code && order.address.country_code !== 'FR'"
                          class="ml-1 text-xs uppercase"
                        >
                          · {{ order.address.country_code }}
                        </span>
                      </p>
                    </div>
                  </td>
                  <td class="text-muted px-3 py-3 align-top">
                    {{ orderSummary(order) }}
                  </td>
                  <td class="text-muted px-3 py-3 align-top whitespace-nowrap">
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
            <p class="text-highlighted text-sm font-medium">Ajouter une étiquette manuelle</p>
            <p class="text-muted text-xs">
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
              <USelect v-model="manual.country_code" :items="COUNTRY_OPTIONS" value-key="value" class="w-full" />
            </UFormField>
          </div>

          <template #footer>
            <div class="flex justify-end">
              <UButton icon="i-lucide-plus" @click="addManual"> Ajouter à la planche </UButton>
            </div>
          </template>
        </UCard>

        <!-- Selected labels -->
        <UCard :ui="{ body: 'p-0 overflow-visible' }">
          <template #header>
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p class="text-highlighted text-sm font-medium">Étiquettes à imprimer</p>
                <p class="text-muted text-xs">
                  {{ labels.length }} colis · {{ labelSlotCount }} vignettes
                  <span v-if="pageCountDetail"> — {{ pageCountDetail }}</span
                  >. Modifications éphémères : la commande eBay d’origine n’est pas modifiée.
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

          <div v-if="labels.length === 0" class="text-muted p-5 text-sm">
            Aucune étiquette sélectionnée pour le moment.
          </div>

          <div v-else class="divide-default divide-y overflow-visible">
            <div
              v-for="label in labels"
              :key="label.uid"
              class="flex flex-col gap-4 overflow-visible p-4 sm:p-5 lg:flex-row lg:items-start lg:gap-4"
            >
              <UBadge :color="label.source === 'ebay' ? 'warning' : 'neutral'" variant="subtle" class="shrink-0">
                {{ label.source === 'ebay' ? `eBay #${label.ebayOrderId?.slice(-6)}` : 'Manuel' }}
              </UBadge>
              <div class="flex min-w-0 flex-1 flex-col gap-3 overflow-visible">
                <div class="grid min-w-0 gap-2 sm:grid-cols-2">
                  <UInput v-model="label.full_name" placeholder="Nom complet" />
                  <UInput v-model="label.line1" placeholder="Adresse" />
                  <UInput v-model="label.line2" placeholder="Complément" />
                  <div class="grid grid-cols-[1fr_2fr] gap-2">
                    <UInput v-model="label.postal_code" placeholder="CP" />
                    <UInput v-model="label.city" placeholder="Ville" />
                  </div>
                  <UInput v-model="label.state" placeholder="État (US/CA)" />
                  <USelect v-model="label.country_code" :items="COUNTRY_OPTIONS" value-key="value" />
                </div>
                <!-- Bloc timbre : présence repérable dans le DOM via data-goupixdex-stamp (vérifiez après rebuild / reload de l’app). -->
                <div
                  data-goupixdex-stamp="pdf-picker"
                  class="border-default bg-elevated/30 min-h-[4.5rem] min-w-0 overflow-visible rounded-lg border border-dashed p-3"
                >
                  <p class="text-highlighted text-sm font-medium">Timbre La Poste (PDF, optionnel)</p>
                  <p class="text-muted mb-3 text-xs leading-snug">
                    PDF depuis laposte.fr ; ajouté sur la planche à taille réelle (page suivante si besoin).
                  </p>
                  <div class="flex flex-wrap items-center gap-2">
                    <input
                      :id="stampPdfInputId(label.uid)"
                      type="file"
                      accept="application/pdf,.pdf"
                      class="sr-only"
                      @change="onStampPdfChange(label.uid, $event)"
                    />
                    <UButton
                      size="sm"
                      color="neutral"
                      variant="outline"
                      icon="i-lucide-file-up"
                      class="shrink-0"
                      @click="openStampPdfPicker(label.uid)"
                    >
                      Choisir un PDF timbre
                    </UButton>
                    <UBadge v-if="label.stamp_pdf_base64" color="success" variant="subtle">PDF sélectionné</UBadge>
                    <UButton
                      v-if="label.stamp_pdf_base64"
                      size="xs"
                      color="neutral"
                      variant="ghost"
                      label="Retirer"
                      class="shrink-0"
                      @click="clearStampPdf(label.uid)"
                    />
                  </div>
                </div>
              </div>
              <UButton
                color="neutral"
                variant="ghost"
                icon="i-lucide-x"
                size="sm"
                class="shrink-0 self-start"
                @click="removeLabel(label.uid)"
              />
            </div>
          </div>

          <template #footer>
            <div class="flex flex-wrap items-center justify-between gap-3">
              <p v-if="previewStale" class="text-warning text-xs">
                <UIcon name="i-lucide-alert-circle" class="mr-1 inline-block size-3.5" />
                L'aperçu n'est plus à jour, régénérez-le.
              </p>
              <span v-else />
              <div class="flex items-center gap-2">
                <UButton
                  icon="i-lucide-eye"
                  :loading="previewLoading"
                  :disabled="labels.length === 0 || pdfBusy"
                  @click="refreshPreview"
                >
                  Générer l'aperçu
                </UButton>
                <UButton
                  icon="i-lucide-download"
                  color="primary"
                  :loading="downloadLoading"
                  :disabled="!canDownloadPdf"
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
            <p class="text-highlighted text-sm font-medium">Aperçu PDF (rendu identique à l'impression)</p>
          </template>
          <iframe :src="previewUrl" class="bg-elevated/40 h-[80vh] w-full" title="Aperçu de la planche d'étiquettes" />
        </UCard>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { ComputedRef, Ref } from 'vue'
import { nextTick } from 'vue'
import type { EbayUnshippedOrder, ShippingLabelInput } from '~/composables/useShippingLabels'
import { apiErrorMessage } from '~/composables/useApiError'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  "Étiquettes d'envoi",
  "Génération d'étiquettes A4 (Avery L7173, 8 par feuille) pour vos envois postaux GoupixDex avec le logo et l'adresse de l'acheteur.",
)

interface LabelRow extends ShippingLabelInput {
  uid: string
  source: 'ebay' | 'manual'
  ebayOrderId: string | null
}

const { fetchEbayOrders, generateLabelsPdf } = useShippingLabels()
const { getSettings } = useSettings()
const toast = useToast()

const orders: Ref<EbayUnshippedOrder[]> = ref([])
const loadingOrders: Ref<boolean> = ref(false)
const ebayUnavailable: Ref<boolean> = ref(false)
const ebayScopeMismatch: Ref<boolean> = ref(false)
const senderAddressComplete: Ref<boolean> = ref(false)
const senderLoading: Ref<boolean> = ref(true)
const labels: Ref<LabelRow[]> = ref([])
const previewUrl: Ref<string | null> = ref(null)
const previewBlob: Ref<Blob | null> = ref(null)
const previewLoading: Ref<boolean> = ref(false)
const downloadLoading: Ref<boolean> = ref(false)
const lastPreviewSignature: Ref<string> = ref('')

const manual = reactive<ShippingLabelInput>({
  full_name: '',
  line1: '',
  line2: '',
  postal_code: '',
  city: '',
  state: '',
  country_code: 'FR',
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
  { value: 'MX', label: 'Mexique' },
] as const

let manualCounter: number = 0

function isEbayScopeMismatchError(e: unknown): boolean {
  const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (detail && typeof detail === 'object' && 'code' in detail) {
    const code = (detail as { code?: string }).code
    return code === 'ebay_scope_mismatch' || code === 'ebay_fulfillment_denied'
  }
  if (typeof detail === 'string') {
    return detail.includes('sell.fulfillment') || detail.includes('ebay_scope_mismatch')
  }
  return false
}

async function loadOrders(): Promise<void> {
  loadingOrders.value = true
  ebayUnavailable.value = false
  ebayScopeMismatch.value = false
  try {
    orders.value = await fetchEbayOrders()
  } catch (e: unknown) {
    const status = (e as { response?: { status?: number } })?.response?.status
    if (status === 400 && isEbayScopeMismatchError(e)) {
      ebayScopeMismatch.value = true
    } else if (status === 400) {
      ebayUnavailable.value = true
    } else {
      toast.add({
        title: 'Impossible de charger les commandes eBay',
        description: apiErrorMessage(e),
        color: 'error',
      })
    }
  } finally {
    loadingOrders.value = false
  }
}

const selectedOrderIds: ComputedRef<Set<string>> = computed(
  () =>
    new Set(
      labels.value.filter((l) => l.source === 'ebay' && l.ebayOrderId != null).map((l) => l.ebayOrderId as string),
    ),
)

function isOrderSelected(orderId: string): boolean {
  return selectedOrderIds.value.has(orderId)
}

function toggleOrder(order: EbayUnshippedOrder): void {
  const uid = `ebay:${order.order_id}`
  const idx = labels.value.findIndex((l) => l.uid === uid)
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
    country_code: order.address.country_code || 'FR',
    stamp_pdf_base64: null,
  })
}

function addManual(): void {
  if (!manual.full_name.trim() || !manual.line1.trim() || !manual.city.trim() || !manual.postal_code.trim()) {
    toast.add({
      title: 'Champs incomplets',
      description: 'Nom, adresse, code postal et ville sont requis.',
      color: 'warning',
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
    country_code: (manual.country_code || 'FR').toUpperCase(),
    stamp_pdf_base64: null,
  })
  manual.full_name = ''
  manual.line1 = ''
  manual.line2 = ''
  manual.postal_code = ''
  manual.city = ''
  manual.state = ''
  manual.country_code = 'FR'
}

function removeLabel(uid: string): void {
  const idx = labels.value.findIndex((l) => l.uid === uid)
  if (idx >= 0) {
    labels.value.splice(idx, 1)
  }
}

function stampFingerprint(b64: string | null | undefined): string {
  if (!b64) return ''
  let h = 2166136261
  const cap = Math.min(b64.length, 12000)
  for (let i = 0; i < cap; i++) {
    h ^= b64.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return `${b64.length}:${h >>> 0}`
}

/** Stable id for the hidden file input (DOM id cannot contain ':' etc.). */
function stampPdfInputId(uid: string): string {
  return `stamp-pdf-${uid.replace(/[^a-zA-Z0-9_-]/g, '-')}`
}

function openStampPdfPicker(uid: string): void {
  void nextTick(() => {
    document.getElementById(stampPdfInputId(uid))?.click()
  })
}

function onStampPdfChange(uid: string, ev: Event): void {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const okMime = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
  if (!okMime) {
    toast.add({
      title: 'PDF requis',
      description: 'Choisissez le fichier PDF du timbre (laposte.fr).',
      color: 'warning',
    })
    input.value = ''
    return
  }
  const maxBytes = 3 * 1024 * 1024
  if (file.size > maxBytes) {
    toast.add({
      title: 'Fichier trop volumineux',
      description: 'PDF timbre limité à 3 Mo.',
      color: 'warning',
    })
    input.value = ''
    return
  }
  const reader = new FileReader()
  reader.onload = (): void => {
    const dataUrl = reader.result as string
    const comma = dataUrl.indexOf(',')
    const b64 = comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl
    const row = labels.value.find((l) => l.uid === uid)
    if (row) {
      row.stamp_pdf_base64 = b64
    }
  }
  reader.readAsDataURL(file)
  input.value = ''
}

function clearStampPdf(uid: string): void {
  const row = labels.value.find((l) => l.uid === uid)
  if (row) {
    row.stamp_pdf_base64 = null
  }
  const input = document.getElementById(stampPdfInputId(uid)) as HTMLInputElement | null
  if (input) {
    input.value = ''
  }
}

function clearAll(): void {
  labels.value.splice(0, labels.value.length)
}

const labelsPayload: ComputedRef<ShippingLabelInput[]> = computed(() =>
  labels.value.map((l) => ({
    full_name: l.full_name,
    line1: l.line1,
    line2: l.line2 || null,
    postal_code: l.postal_code,
    city: l.city,
    state: l.state || null,
    country_code: l.country_code || 'FR',
    stamp_pdf_base64: l.stamp_pdf_base64 ?? null,
  })),
)

const labelsSignature: ComputedRef<string> = computed(() =>
  JSON.stringify({
    rows: labels.value.map((l) => ({
      full_name: l.full_name,
      line1: l.line1,
      line2: l.line2 || null,
      postal_code: l.postal_code,
      city: l.city,
      state: l.state || null,
      country_code: l.country_code || 'FR',
      stamp: stampFingerprint(l.stamp_pdf_base64 ?? null),
    })),
  }),
)

const previewStale: ComputedRef<boolean> = computed(
  () => Boolean(previewUrl.value) && labelsSignature.value !== lastPreviewSignature.value,
)

const pdfBusy: ComputedRef<boolean> = computed(() => previewLoading.value || downloadLoading.value)

/** Download button enabled whenever there is at least one label row (preview not required). */
const canDownloadPdf: ComputedRef<boolean> = computed(() => labels.value.length > 0 && !downloadLoading.value)

function revokePreview(): void {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
  }
  previewUrl.value = null
  previewBlob.value = null
  lastPreviewSignature.value = ''
}

async function refreshPreview(): Promise<void> {
  if (labels.value.length === 0) {
    toast.add({
      title: 'Aucune étiquette',
      description: 'Sélectionnez une commande ou ajoutez une étiquette manuelle.',
      color: 'warning',
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
      color: 'error',
    })
  } finally {
    previewLoading.value = false
  }
}

async function downloadPdf(): Promise<void> {
  if (labels.value.length === 0) {
    toast.add({
      title: 'Aucune étiquette',
      description: 'Sélectionnez une commande ou ajoutez une étiquette manuelle.',
      color: 'warning',
    })
    return
  }
  downloadLoading.value = true
  try {
    const blob = await generateLabelsPdf(labelsPayload.value)
    const stamp = new Date().toISOString().slice(0, 10)
    const dlUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = dlUrl
    a.download = `goupixdex-etiquettes-${stamp}.pdf`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(dlUrl)

    revokePreview()
    previewBlob.value = blob
    previewUrl.value = URL.createObjectURL(blob)
    lastPreviewSignature.value = labelsSignature.value
  } catch (e) {
    toast.add({
      title: 'Téléchargement impossible',
      description: apiErrorMessage(e),
      color: 'error',
    })
  } finally {
    downloadLoading.value = false
  }
}

const LABELS_PER_PAGE = 8

/** With sender configured: 2 L7173 stickers per parcel (recipient then sender on separate physical labels). */
const labelSlotCount: ComputedRef<number> = computed(() => {
  const n = labels.value.length
  if (n === 0) return 0
  return senderAddressComplete.value ? n * 2 : n
})

const pageCountDetail: ComputedRef<string> = computed(() => {
  const n = labels.value.length
  if (n === 0) {
    return ''
  }
  const slots = senderAddressComplete.value ? n * 2 : n
  const pages = Math.ceil(slots / LABELS_PER_PAGE)
  const pagesWord = pages > 1 ? 'pages' : 'page'
  if (!senderAddressComplete.value) {
    return `${pages} ${pagesWord} A4 (aperçu destinataires seuls ; PDF complet après config. expéditeur)`
  }
  return `${pages} ${pagesWord} A4 (${slots} vignettes : ${n} destinataire${n > 1 ? 's' : ''} + ${n} expéditeur${n > 1 ? 's' : ''})`
})

async function loadSenderSettings(): Promise<void> {
  senderLoading.value = true
  try {
    const s = await getSettings()
    senderAddressComplete.value = s.sender_address_complete === true
  } catch {
    senderAddressComplete.value = false
  } finally {
    senderLoading.value = false
  }
}

onMounted((): void => {
  void loadOrders()
  void loadSenderSettings()
})

onBeforeUnmount((): void => {
  revokePreview()
})

function formatOrderDate(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
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
