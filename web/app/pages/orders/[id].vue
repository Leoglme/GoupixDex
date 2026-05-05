<template>
  <UDashboardPanel :id="`order-${id}`">
    <template #header>
      <UDashboardNavbar :title="navbarTitle">
        <template #leading>
          <UDashboardSidebarCollapse />
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

          <UCard class="ring-default/60 shadow-sm ring-1" :ui="{ body: 'p-5 sm:p-6 space-y-4' }">
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

          <UCard class="ring-default/60 shadow-sm ring-1" :ui="{ body: 'p-0 sm:p-0' }">
            <div class="border-default border-b px-4 py-3 sm:px-5">
              <p class="text-highlighted text-sm font-medium">Lignes d’achat</p>
              <p class="text-muted text-xs">Articles liés à vos fiches GoupixDex et statut de vente.</p>
            </div>
            <div class="overflow-x-auto">
              <table class="min-w-full border-separate border-spacing-0 text-sm">
                <thead class="bg-elevated/60 text-muted text-left text-xs uppercase">
                  <tr>
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
</template>

<script setup lang="ts">
import type { ComputedRef, Ref } from 'vue'
import type { OrderDetail, OrderDetailLine } from '~/types/Orders'
import { cardmarketSellerProfileUrl } from '~/utils/cardmarket'
import { countryFlagImgUrl } from '~/utils/flagEmoji'

definePageMeta({ middleware: 'auth' })

const route = useRoute()
const { getOrder } = useOrders()
const toast = useToast()

const order: Ref<OrderDetail | null> = ref(null)
const loading: Ref<boolean> = ref(true)

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
 * Derive a readable Pokémon label from structured line fields.
 * @param ln - Purchase line.
 * @returns Title-case-ish card label.
 */
function formatPokemonLabel(ln: OrderDetailLine): string {
  const raw = ln.raw_label || ''
  const first = raw.split(/\s+\d+(?:\/\d+)?\s+[A-Z]{2}\s+/)[0]
  if (first && /^\d+\s/.test(first.trim())) {
    return first.replace(/^\d+\s+/, '').trim() || ln.pokemon_key || raw
  }
  return ln.pokemon_key || raw.slice(0, 80) || '—'
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
