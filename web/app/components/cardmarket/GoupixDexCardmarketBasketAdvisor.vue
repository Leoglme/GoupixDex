<template>
  <UCard class="ring-default/60 shadow-sm ring-1">
    <template #header>
      <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p class="text-highlighted font-medium">Conseil panier</p>
          <p class="text-muted text-xs">
            À budget fixé, sélection des vendeurs au meilleur rapport cartes / € — en limitant le nombre de paquets
            (frais de port) et le surcoût par carte.
          </p>
        </div>
      </div>
    </template>

    <div class="space-y-5 p-4 sm:p-6">
      <div class="flex flex-wrap items-end gap-3">
        <UFormField label="Budget" hint="Plafond du panier (cartes uniquement, hors port)" class="grow sm:grow-0">
          <UInput
            v-model.number="budgetEur"
            type="number"
            min="0"
            step="1"
            class="w-32"
            :ui="{ trailing: 'pe-2 text-muted text-xs' }"
          >
            <template #trailing>€</template>
          </UInput>
        </UFormField>
        <UFormField
          label="Min cartes / nouveau vendeur"
          hint="Évite les vendeurs qui n'apportent qu'une carte (frais de port pour rien)"
        >
          <UInput v-model.number="minPicksPerNewSeller" type="number" min="1" step="1" class="w-24" />
        </UFormField>
        <UFormField
          label="Surcoût max / carte"
          hint="% accepté vs prix mini, uniquement chez un NOUVEAU vendeur (existant : pas de limite)"
        >
          <UInput
            v-model.number="maxOverpayPercentPerCard"
            type="number"
            min="0"
            step="5"
            placeholder="ex. 50"
            class="w-24"
            :ui="{ trailing: 'pe-2 text-muted text-xs' }"
          >
            <template #trailing>%</template>
          </UInput>
        </UFormField>
        <UFormField label="Max vendeurs" hint="0 = pas de limite">
          <UInput v-model.number="maxSellers" type="number" min="0" step="1" class="w-24" />
        </UFormField>
        <UFormField label="Compléter avec vendeurs 1-carte" hint="Brûle le budget restant, ajoute des frais de port">
          <USwitch v-model="allowSinglePickSellers" />
        </UFormField>
      </div>

      <div v-if="suggestion" class="space-y-4">
        <div class="grid gap-3 sm:grid-cols-4">
          <div class="bg-elevated/40 ring-default/60 rounded-lg p-3 ring-1">
            <p class="text-muted text-xs">Cartes couvertes</p>
            <p class="text-highlighted text-lg font-semibold tabular-nums">
              {{ suggestion.covered_cards }} / {{ suggestion.total_cards }}
            </p>
          </div>
          <div class="bg-elevated/40 ring-default/60 rounded-lg p-3 ring-1">
            <p class="text-muted text-xs">Total panier</p>
            <p class="text-highlighted text-lg font-semibold tabular-nums">
              {{ formatPrice(suggestion.total_price_eur) }}
            </p>
          </div>
          <div class="bg-elevated/40 ring-default/60 rounded-lg p-3 ring-1">
            <p class="text-muted text-xs">Vendeurs</p>
            <p class="text-highlighted text-lg font-semibold tabular-nums">
              {{ suggestion.sellers.length }}
              <span v-if="suggestion.single_pick_seller_count > 0" class="text-warning ml-1 text-xs font-normal">
                ({{ suggestion.single_pick_seller_count }} à 1 carte)
              </span>
            </p>
          </div>
          <div class="bg-elevated/40 ring-default/60 rounded-lg p-3 ring-1">
            <p class="text-muted text-xs">Budget restant</p>
            <p class="text-highlighted text-lg font-semibold tabular-nums">
              {{ formatPrice(suggestion.remaining_budget_eur) }}
            </p>
          </div>
        </div>

        <UAlert
          v-for="(w, i) in suggestion.warnings"
          :key="`adv-warn-${i}`"
          color="warning"
          variant="subtle"
          icon="i-lucide-alert-triangle"
          :description="w"
        />

        <div v-if="suggestion.sellers.length" class="space-y-3">
          <p class="text-muted text-xs tracking-wide uppercase">Plan d’achat</p>
          <div
            v-for="group in suggestion.sellers"
            :key="`adv-${group.seller_name}`"
            class="border-default rounded-lg border p-3 sm:p-4"
          >
            <div class="flex flex-wrap items-baseline justify-between gap-2">
              <a
                v-if="sellerHref(group.seller_name)"
                :href="sellerHref(group.seller_name) || ''"
                target="_blank"
                rel="noopener noreferrer"
                class="text-primary max-w-[16rem] truncate font-medium underline-offset-2 hover:underline"
              >
                {{ group.seller_name }}
              </a>
              <span v-else class="text-highlighted font-medium">{{ group.seller_name }}</span>
              <span class="text-muted text-xs tabular-nums">
                {{ group.picks.length }} carte{{ group.picks.length > 1 ? 's' : '' }} ·
                {{ formatPrice(group.subtotal_eur) }}
              </span>
            </div>
            <ul class="mt-2 space-y-1">
              <li
                v-for="pick in group.picks"
                :key="`${group.seller_name}-${pick.code}`"
                class="text-muted flex flex-wrap items-baseline gap-x-2 text-xs"
              >
                <a
                  v-if="pick.product_url"
                  :href="pick.product_url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="text-default font-medium underline-offset-2 hover:underline"
                >
                  {{ pick.product_name || pick.code }}
                </a>
                <span v-else class="text-default font-medium">{{ pick.product_name || pick.code }}</span>
                <span class="tabular-nums">{{ formatPrice(pick.price_eur) }}</span>
                <span v-if="pick.is_best_price" class="text-success">meilleur prix</span>
                <span v-else-if="typeof pick.delta_vs_min_percent === 'number'" class="text-warning">
                  +{{ pick.delta_vs_min_percent.toFixed(2) }} %
                </span>
              </li>
            </ul>
          </div>
        </div>
        <div v-else class="text-muted px-2 py-4 text-center text-xs">
          Aucun vendeur ne rentre dans le budget actuel.
        </div>

        <div v-if="suggestion.missing.length" class="space-y-2">
          <p class="text-muted text-xs tracking-wide uppercase">Non couvertes ({{ suggestion.missing.length }})</p>
          <ul class="text-muted list-disc space-y-1 pl-5 text-xs">
            <li v-for="m in suggestion.missing" :key="`miss-${m.code}`">
              <span class="text-default font-medium">{{ m.product_name || m.code }}</span>
              <span v-if="m.cheapest_eur !== null" class="ml-1 tabular-nums">
                — min {{ formatPrice(m.cheapest_eur) }}
              </span>
              <span class="ml-1">({{ missingReasonLabel(m.reason) }})</span>
            </li>
          </ul>
        </div>
      </div>
      <div v-else class="text-muted px-2 py-4 text-center text-xs">
        Saisissez un budget pour générer une suggestion.
      </div>
    </div>
  </UCard>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { CardmarketBasketMissing, CardmarketBasketSuggestion, CardmarketCardRaw } from '~/types/CardmarketSearch'
import { cardmarketSellerProfileUrl } from '~/utils/cardmarket'
import { suggestCardmarketBasket } from '~/utils/cardmarketBasketOptimizer'

const props = defineProps<{
  cards: CardmarketCardRaw[]
  defaultBudgetEur?: number
}>()

const STORAGE_KEY = 'goupix_cardmarket_basket_advisor'

interface Persisted {
  budgetEur: number
  minPicksPerNewSeller: number
  maxOverpayPercentPerCard: number | null
  maxSellers: number
  allowSinglePickSellers: boolean
}

function loadPrefs(): Partial<Persisted> | null {
  if (!import.meta.client) {
    return null
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      return null
    }
    const p = JSON.parse(raw) as Record<string, unknown>
    const out: Partial<Persisted> = {}
    if (typeof p.budgetEur === 'number' && Number.isFinite(p.budgetEur) && p.budgetEur >= 0) {
      out.budgetEur = p.budgetEur
    }
    if (
      typeof p.minPicksPerNewSeller === 'number' &&
      Number.isFinite(p.minPicksPerNewSeller) &&
      p.minPicksPerNewSeller >= 1
    ) {
      out.minPicksPerNewSeller = Math.floor(p.minPicksPerNewSeller)
    }
    if (p.maxOverpayPercentPerCard === null) {
      out.maxOverpayPercentPerCard = null
    } else if (
      typeof p.maxOverpayPercentPerCard === 'number' &&
      Number.isFinite(p.maxOverpayPercentPerCard) &&
      p.maxOverpayPercentPerCard >= 0
    ) {
      out.maxOverpayPercentPerCard = p.maxOverpayPercentPerCard
    }
    if (typeof p.maxSellers === 'number' && Number.isFinite(p.maxSellers) && p.maxSellers >= 0) {
      out.maxSellers = Math.floor(p.maxSellers)
    }
    if (typeof p.allowSinglePickSellers === 'boolean') {
      out.allowSinglePickSellers = p.allowSinglePickSellers
    }
    return Object.keys(out).length ? out : null
  } catch {
    return null
  }
}

function savePrefs(p: Persisted): void {
  if (!import.meta.client) {
    return
  }
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(p))
  } catch {
    /* quota / private mode */
  }
}

const persisted = loadPrefs()

const budgetEur = ref<number>(
  typeof persisted?.budgetEur === 'number' ? persisted.budgetEur : (props.defaultBudgetEur ?? 65),
)
const minPicksPerNewSeller = ref<number>(
  typeof persisted?.minPicksPerNewSeller === 'number' ? persisted.minPicksPerNewSeller : 2,
)
const maxOverpayPercentPerCard = ref<number | null>(
  persisted && 'maxOverpayPercentPerCard' in persisted ? (persisted.maxOverpayPercentPerCard ?? null) : 80,
)
const maxSellers = ref<number>(typeof persisted?.maxSellers === 'number' ? persisted.maxSellers : 0)
const allowSinglePickSellers = ref<boolean>(
  typeof persisted?.allowSinglePickSellers === 'boolean' ? persisted.allowSinglePickSellers : false,
)

function missingReasonLabel(reason: CardmarketBasketMissing['reason']): string {
  if (reason === 'no_offer') {
    return 'aucune offre'
  }
  if (reason === 'overpriced') {
    return 'surcoût trop élevé'
  }
  return 'hors budget'
}

const eurFmt = new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' })

function formatPrice(n: unknown): string {
  const x = typeof n === 'number' ? n : Number(n)
  if (!Number.isFinite(x)) {
    return '—'
  }
  return eurFmt.format(x)
}

function sellerHref(name: string): string | null {
  return cardmarketSellerProfileUrl(name)
}

function normalizedOverpayPct(): number | null {
  const v = maxOverpayPercentPerCard.value
  if (v === null || v === undefined) {
    return null
  }
  const n = Number(v)
  if (!Number.isFinite(n) || n < 0) {
    return null
  }
  return n
}

const suggestion = computed<CardmarketBasketSuggestion | null>(() => {
  const cards = Array.isArray(props.cards) ? props.cards : []
  if (!cards.length) {
    return null
  }
  return suggestCardmarketBasket(cards, {
    budgetEur: Number(budgetEur.value) || 0,
    minPicksPerNewSeller: Number(minPicksPerNewSeller.value) || 1,
    maxOverpayPercentPerCard: normalizedOverpayPct(),
    maxSellers: Number(maxSellers.value) || 0,
    allowSinglePickSellers: allowSinglePickSellers.value === true,
  })
})

watch(
  [budgetEur, minPicksPerNewSeller, maxOverpayPercentPerCard, maxSellers, allowSinglePickSellers],
  ([b, m, o, s, a]) => {
    savePrefs({
      budgetEur: Number(b) || 0,
      minPicksPerNewSeller: Number(m) || 1,
      maxOverpayPercentPerCard: o === null || o === undefined ? null : Number(o) || 0,
      maxSellers: Number(s) || 0,
      allowSinglePickSellers: a === true,
    })
  },
  { flush: 'post' },
)
</script>
