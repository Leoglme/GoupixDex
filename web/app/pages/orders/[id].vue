<template>
  <UDashboardPanel :id="`order-${id}`">
    <template #header>
      <UDashboardNavbar :title="navbarTitle">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <div v-if="order" class="flex flex-wrap items-center gap-2">
            <input
              ref="reimportInputRef"
              type="file"
              accept="application/pdf"
              class="hidden"
              @change="onReimportFileSelected"
            />
            <UButton
              color="neutral"
              variant="soft"
              icon="i-lucide-file-input"
              :loading="reimporting"
              @click="openReimportPicker"
            >
              Réimporter le PDF
            </UButton>
          </div>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="w-full space-y-6 p-4 sm:p-6">
        <div v-if="loading" class="flex justify-center py-20">
          <UIcon name="i-lucide-loader-2" class="text-primary size-10 animate-spin" />
        </div>

        <template v-else-if="order">
          <div class="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p class="text-primary text-xs font-medium tracking-wide uppercase">Commande Cardmarket</p>
              <h1 class="text-highlighted text-2xl font-semibold tracking-tight">#{{ order.external_order_id }}</h1>
              <p v-if="order.source_filename" class="text-muted text-xs">Fichier : {{ order.source_filename }}</p>
            </div>
            <div class="flex flex-wrap items-center gap-2">
              <span v-if="countryFlagSrc" class="inline-flex items-center gap-2">
                <img
                  :src="countryFlagSrc"
                  alt=""
                  width="30"
                  height="23"
                  class="inline-block h-[23px] w-[30px] shrink-0 rounded-sm object-cover"
                  loading="lazy"
                  decoding="async"
                />
                <span class="sr-only">{{ order.seller_country_code }}</span>
              </span>
              <span v-else class="text-muted text-sm">—</span>
              <UBadge color="primary" variant="subtle">
                {{ order.sold_articles_count }} article(s) vendu(s) sur {{ totalUnits }}
              </UBadge>
            </div>
          </div>

          <UPageGrid class="grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5">
            <UPageCard
              icon="i-lucide-credit-card"
              title="Payé le"
              variant="subtle"
              class="min-w-0 rounded-lg"
              :ui="{
                leading: 'p-2.5 rounded-full bg-primary/10 ring ring-inset ring-primary/25 flex-col',
                title: 'font-normal text-muted text-xs uppercase',
              }"
            >
              <p class="text-highlighted text-base font-semibold tabular-nums sm:text-lg">
                {{ formatWhen(order.paid_at) }}
              </p>
            </UPageCard>
            <UPageCard
              icon="i-lucide-truck"
              title="Envoyé le"
              variant="subtle"
              class="min-w-0 rounded-lg"
              :ui="{
                leading: 'p-2.5 rounded-full bg-info/10 ring ring-inset ring-info/25 flex-col',
                title: 'font-normal text-muted text-xs uppercase',
              }"
            >
              <p class="text-highlighted text-base font-semibold tabular-nums sm:text-lg">
                {{ formatWhen(order.shipped_at) }}
              </p>
            </UPageCard>
            <UPageCard
              icon="i-lucide-package-check"
              title="Livré le"
              variant="subtle"
              class="min-w-0 rounded-lg"
              :ui="{
                leading: 'p-2.5 rounded-full bg-success/10 ring ring-inset ring-success/25 flex-col',
                title: 'font-normal text-muted text-xs uppercase',
              }"
            >
              <p class="text-highlighted text-base font-semibold tabular-nums sm:text-lg">
                {{ formatWhen(order.delivered_at) }}
              </p>
            </UPageCard>
            <UPageCard
              icon="i-lucide-wallet"
              title="Total TTC"
              variant="subtle"
              class="min-w-0 rounded-lg"
              :ui="{
                leading: 'p-2.5 rounded-full bg-warning/10 ring ring-inset ring-warning/25 flex-col',
                title: 'font-normal text-muted text-xs uppercase',
              }"
            >
              <p class="text-highlighted text-base font-semibold tabular-nums sm:text-lg">
                {{ eur.format(order.order_total) }}
              </p>
            </UPageCard>
            <UPageCard
              icon="i-lucide-trending-up"
              title="CA Ventes"
              variant="subtle"
              class="min-w-0 rounded-lg"
              :ui="{
                leading: 'p-2.5 rounded-full bg-success/10 ring ring-inset ring-success/25 flex-col',
                title: 'font-normal text-muted text-xs uppercase',
              }"
            >
              <p class="text-highlighted text-base font-semibold tabular-nums sm:text-lg">
                {{ eur.format(order.sales_revenue_eur ?? 0) }}
              </p>
            </UPageCard>
          </UPageGrid>

          <UCard class="ring-default ring-1" :ui="{ body: 'p-5 sm:p-6 space-y-4' }">
            <div class="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <p class="text-muted text-xs font-medium uppercase">Vendeur</p>
                <p class="text-highlighted mt-1 font-medium">
                  <a
                    v-if="sellerProfileUrl"
                    :href="sellerProfileUrl"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="text-primary hover:text-primary/85 underline-offset-2 hover:underline"
                  >
                    {{ order.seller_username }}
                  </a>
                  <template v-else>{{ order.seller_username || '—' }}</template>
                </p>
                <p v-if="order.seller_display_name" class="text-muted text-sm">{{ order.seller_display_name }}</p>
              </div>
              <div>
                <p class="text-muted text-xs font-medium uppercase">Valeur articles</p>
                <p class="text-highlighted mt-1 text-lg font-semibold tabular-nums">
                  {{ eur.format(order.items_subtotal) }}
                </p>
              </div>
              <div>
                <p class="text-muted text-xs font-medium uppercase">Frais de port</p>
                <p class="text-highlighted mt-1 text-lg font-semibold tabular-nums">
                  {{ eur.format(order.shipping_fee) }}
                </p>
              </div>
              <div>
                <p class="text-muted text-xs font-medium uppercase">Total</p>
                <p class="text-highlighted mt-1 text-lg font-semibold tabular-nums">
                  {{ eur.format(order.order_total) }}
                </p>
              </div>
            </div>
            <p class="text-muted text-xs leading-relaxed">
              Les frais de port sont stockés pour référence ; ils ne sont pas inclus dans les calculs de marge pour
              l’instant.
            </p>
          </UCard>

          <UCard class="ring-default ring-1" :ui="{ body: 'p-0 sm:p-0' }">
            <div class="border-default border-b px-4 py-3 sm:px-5">
              <p class="text-highlighted text-sm font-medium">Lignes d’achat</p>
              <p class="text-muted text-xs">
                Cliquez sur le crayon pour corriger une ligne, ou réimportez le PDF pour fusionner les changements.
              </p>
            </div>
            <div class="overflow-x-auto">
              <table class="min-w-full border-separate border-spacing-0 text-sm">
                <thead class="bg-elevated/60 text-muted text-left text-xs uppercase">
                  <tr>
                    <th class="border-default w-10 border-b px-4 py-2 font-medium" />
                    <th class="border-default border-b px-4 py-2 font-medium">Qté</th>
                    <th class="border-default border-b px-4 py-2 font-medium">Carte</th>
                    <th class="border-default border-b px-4 py-2 font-medium">Set</th>
                    <th class="border-default border-b px-4 py-2 font-medium">N°</th>
                    <th class="border-default border-b px-4 py-2 font-medium">État</th>
                    <th class="border-default border-b px-4 py-2 text-end font-medium">Prix unit.</th>
                    <th class="border-default border-b px-4 py-2 font-medium">Stock restant</th>
                    <th class="border-default border-b px-4 py-2 font-medium">Lié à</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="ln in order.lines" :key="ln.id" class="border-default hover:bg-elevated/40 border-t">
                    <td class="border-default border-b px-2 py-3 align-middle">
                      <UButton
                        color="neutral"
                        variant="ghost"
                        size="xs"
                        icon="i-lucide-pencil"
                        aria-label="Modifier la ligne"
                        @click="openEditLine(ln)"
                      />
                    </td>
                    <td class="border-default border-b px-4 py-3 align-middle tabular-nums">{{ ln.quantity }}</td>
                    <td class="text-highlighted border-default border-b px-4 py-3 align-middle font-medium">
                      {{ formatPokemonLabel(ln) }}
                    </td>
                    <td class="text-muted border-default border-b px-4 py-3 align-middle">
                      {{ ln.set_code || '—' }}
                    </td>
                    <td class="border-default border-b px-4 py-3 align-middle tabular-nums">
                      {{ ln.card_number || '—' }}
                    </td>
                    <td class="text-muted border-default border-b px-4 py-3 align-middle text-xs">
                      {{ ln.language_code }} · {{ ln.condition_label }}
                    </td>
                    <td class="border-default border-b px-4 py-3 text-end align-middle tabular-nums">
                      {{ eur.format(ln.unit_price_eur) }}
                    </td>
                    <td class="border-default border-b px-4 py-3 align-middle tabular-nums">
                      {{ ln.remaining_units }}
                    </td>
                    <td class="border-default border-b px-4 py-3 align-middle">
                      <div v-if="ln.articles?.length" class="flex flex-col gap-1">
                        <NuxtLink
                          v-for="a in ln.articles"
                          :key="a.id"
                          :to="`/articles/${a.id}`"
                          class="text-primary hover:text-primary/80 text-xs font-medium underline-offset-2 hover:underline"
                        >
                          {{ a.title.slice(0, 42) }}{{ a.title.length > 42 ? '…' : '' }}
                          <span v-if="a.is_sold && a.sold_at" class="text-muted">
                            · vendu {{ formatWhen(a.sold_at) }}
                          </span>
                        </NuxtLink>
                      </div>
                      <span v-else class="text-muted text-xs">—</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </UCard>
        </template>
      </div>
    </template>
  </UDashboardPanel>

  <GoupixDexOrderLineEditModal
    v-model:open="editOpen"
    :line="editLine"
    :pokemon-label="editLine ? formatPokemonLabel(editLine) : ''"
    :submitting="editSubmitting"
    @submit="onEditSubmit"
  />

  <GoupixDexOrderReimportLinkedModal
    v-model:open="reimportConfirmOpen"
    :pending="reimportPending"
    :submitting="reimporting"
    @confirm="onReimportConfirmLinked"
    @ignore="onReimportIgnoreLinked"
  />
</template>

<script setup lang="ts">
import type { OrderLineEditPayload } from '~/components/orders/GoupixDexOrderLineEditModal.vue'
import type { ComputedRef, Ref } from 'vue'
import type { OrderDetail, OrderDetailLine, OrderReimportLineDiff } from '~/types/Orders'
import { cardmarketSellerProfileUrl } from '~/utils/cardmarket'
import { countryFlagImgUrl } from '~/utils/flagEmoji'

definePageMeta({ middleware: 'auth' })

const route = useRoute()
const { getOrder, updateOrderLine, reimportOrderPdf } = useOrders()
const toast = useToast()

const order: Ref<OrderDetail | null> = ref(null)
const loading: Ref<boolean> = ref(true)
const editOpen: Ref<boolean> = ref(false)
const editLine: Ref<OrderDetailLine | null> = ref(null)
const editSubmitting: Ref<boolean> = ref(false)
const reimporting: Ref<boolean> = ref(false)
const reimportConfirmOpen: Ref<boolean> = ref(false)
const reimportPending: Ref<OrderReimportLineDiff[]> = ref([])
const reimportInputRef: Ref<HTMLInputElement | null> = ref(null)
const pendingReimportFile: Ref<File | null> = ref(null)

const id: ComputedRef<number> = computed(() => Number(route.params.id))

const eur: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
})

const navbarTitle: ComputedRef<string> = computed(() =>
  order.value ? `Commande #${order.value.external_order_id}` : 'Commande',
)

const totalUnits: ComputedRef<number> = computed(() => {
  if (!order.value) {
    return 0
  }
  return order.value.lines.reduce((acc, ln) => acc + ln.quantity, 0)
})

const countryFlagSrc: ComputedRef<string | null> = computed(() =>
  countryFlagImgUrl(order.value?.seller_country_code ?? null),
)

const sellerProfileUrl: ComputedRef<string | null> = computed(() =>
  cardmarketSellerProfileUrl(order.value?.seller_username ?? null),
)

/**
 * Format ISO timestamps for French display.
 * @param iso - Nullable API datetime.
 * @returns Short French date or em dash.
 */
function formatWhen(iso: string | null): string {
  if (!iso) {
    return '—'
  }
  try {
    return new Date(iso).toLocaleString('fr-FR')
  } catch {
    return '—'
  }
}

/**
 * Human-readable label from normalized pokemon_key or raw PDF line.
 * @param ln - Purchase line.
 * @returns Display name.
 */
function formatPokemonLabel(ln: OrderDetailLine): string {
  if (ln.pokemon_key) {
    return ln.pokemon_key
      .split(' ')
      .map((w) => (w ? w.charAt(0).toUpperCase() + w.slice(1) : ''))
      .join(' ')
  }
  const raw = ln.raw_label || ''
  const first = raw.split(/\s+\d+(?:\/\d+)?\s+[A-Z]{2}\s+/)[0]
  if (first && /^\d+\s/.test(first.trim())) {
    return first.replace(/^\d+\s+/, '').trim() || raw
  }
  return raw.slice(0, 80) || '—'
}

function openEditLine(ln: OrderDetailLine): void {
  editLine.value = ln
  editOpen.value = true
}

async function onEditSubmit(payload: OrderLineEditPayload): Promise<void> {
  if (!editLine.value) {
    return
  }
  editSubmitting.value = true
  try {
    order.value = await updateOrderLine(editLine.value.id, {
      pokemon_name: payload.pokemon_name,
      set_code: payload.set_code,
      card_number: payload.card_number,
      language_code: payload.language_code,
      condition_label: payload.condition_label,
      unit_price_eur: payload.unit_price_eur,
      quantity: payload.quantity,
    })
    editOpen.value = false
    toast.add({ title: 'Ligne mise à jour', color: 'success' })
  } catch (e) {
    toast.add({ title: 'Échec de la mise à jour', description: apiErrorMessage(e), color: 'error' })
  } finally {
    editSubmitting.value = false
  }
}

function openReimportPicker(): void {
  reimportInputRef.value?.click()
}

function applyOrderFromReimport(detail: OrderDetail): void {
  const summary = detail.reimport_summary
  const { reimport_summary: _drop, ...rest } = detail
  order.value = rest as OrderDetail

  if (!summary) {
    return
  }
  const updated = summary.updated_line_indexes.length + summary.added_line_indexes.length
  if (updated > 0) {
    toast.add({
      title: 'PDF fusionné',
      description: `${updated} ligne(s) mise(s) à jour.`,
      color: 'success',
    })
  }
}

async function runReimport(file: File, confirmIndexes: number[] = []): Promise<void> {
  reimporting.value = true
  try {
    const detail = await reimportOrderPdf(id.value, file, confirmIndexes)
    applyOrderFromReimport(detail)
    const pending = detail.reimport_summary?.pending_linked ?? []
    if (pending.length > 0) {
      reimportPending.value = pending
      pendingReimportFile.value = file
      reimportConfirmOpen.value = true
    } else if ((detail.reimport_summary?.updated_line_indexes.length ?? 0) === 0 && confirmIndexes.length === 0) {
      toast.add({ title: 'Aucun changement détecté dans le PDF', color: 'neutral' })
    }
  } catch (e) {
    toast.add({ title: 'Réimport échoué', description: apiErrorMessage(e), color: 'error' })
  } finally {
    reimporting.value = false
  }
}

async function onReimportFileSelected(ev: Event): Promise<void> {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) {
    return
  }
  await runReimport(file)
}

function onReimportIgnoreLinked(): void {
  pendingReimportFile.value = null
  reimportPending.value = []
}

async function onReimportConfirmLinked(indexes: number[]): Promise<void> {
  const file = pendingReimportFile.value
  if (!file || indexes.length === 0) {
    reimportConfirmOpen.value = false
    pendingReimportFile.value = null
    return
  }
  await runReimport(file, indexes)
  reimportConfirmOpen.value = false
  pendingReimportFile.value = null
  reimportPending.value = []
}

async function load(): Promise<void> {
  loading.value = true
  try {
    order.value = await getOrder(id.value)
  } catch (e) {
    toast.add({ title: 'Commande introuvable', description: apiErrorMessage(e), color: 'error' })
    await navigateTo('/orders')
  } finally {
    loading.value = false
  }
}

useSeoMeta({
  title: computed(() =>
    order.value ? `Commande #${order.value.external_order_id} · GoupixDex` : 'Commande · GoupixDex',
  ),
  description: computed(() =>
    order.value
      ? `Détail de la commande Cardmarket #${order.value.external_order_id}, lignes et articles associés.`
      : 'Commande Cardmarket importée.',
  ),
})

onMounted((): void => {
  void load()
})
</script>
