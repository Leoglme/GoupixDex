<template>
  <UDashboardPanel id="amazon-invites">
    <template #header>
      <UDashboardNavbar title="Invitations Amazon">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="w-full space-y-6 px-4 py-6 sm:space-y-8 sm:px-6 sm:py-8">
        <div
          class="border-default from-primary/10 via-elevated/60 to-primary/5 relative overflow-hidden rounded-2xl border bg-gradient-to-br px-5 py-5 sm:px-7 sm:py-7"
        >
          <div class="bg-primary/10 pointer-events-none absolute -top-16 -right-16 size-48 rounded-full blur-3xl" />
          <div class="bg-primary/5 pointer-events-none absolute -bottom-24 -left-10 size-44 rounded-full blur-3xl" />
          <div class="relative flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div class="max-w-2xl space-y-2">
              <p class="text-primary text-xs font-medium tracking-wide uppercase">Amazon · Pokémon</p>
              <div class="flex flex-wrap items-center gap-2">
                <h1 class="text-highlighted text-xl font-semibold tracking-tight sm:text-2xl">Invitations produits</h1>
                <UBadge v-if="connectionBadge" :color="connectionBadge.color" variant="subtle" class="shrink-0">
                  {{ connectionBadge.label }}
                </UBadge>
              </div>
              <p class="text-muted text-sm leading-relaxed sm:text-base">
                Ici figurent les produits Pokémon proposés par Amazon sur invitation. Chaque fiche rappelle l’état de
                votre demande : acceptée, en attente ou expirée. Lorsque vous pouvez encore poser une demande, un bouton
                sur la fiche ouvre la page Amazon adaptée, sans quitter GoupixDex. Pensez à « Actualiser » pour
                synchroniser la liste.
              </p>
            </div>
            <div
              class="bg-primary/15 text-primary hidden size-24 shrink-0 items-center justify-center rounded-2xl lg:flex"
            >
              <UIcon name="i-simple-icons-amazon" class="size-12" />
            </div>
          </div>
        </div>

        <GoupixDexAmazonSessionBanner :session="session" :loading="loading" />

        <UCard class="ring-default/60 shadow-sm ring-1">
          <template #header>
            <div class="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
              <p class="text-highlighted font-medium">Invitations</p>
              <p v-if="refreshedAt" class="text-muted text-xs">
                Dernière récupération : {{ new Date(refreshedAt).toLocaleString('fr-FR') }}
              </p>
            </div>
          </template>

          <GoupixDexAmazonInvitesToolbar
            v-model:optional-search="optionalSearch"
            v-model:max-pages="maxPages"
            v-model:search-query="searchQuery"
            v-model:hide-expired="hideExpired"
            v-model:status-filter="statusFilter"
            :loading="loading"
            :refreshing="refreshing"
            :result-count="displayItems.length"
            :total-loaded="items.length"
            :status-select-items="statusSelectItems"
            @refresh="refresh"
          />
        </UCard>

        <UAlert
          v-if="error"
          color="error"
          variant="subtle"
          icon="i-lucide-alert-triangle"
          title="Impossible de charger la liste"
          :description="error"
        />

        <GoupixDexAmazonRefreshProgress v-if="refreshing" :phase-hint="refreshPhaseHint" :log-lines="refreshLogLines" />

        <div v-if="refreshing" class="space-y-3">
          <p v-if="streamingDisplayItems.length" class="text-muted text-xs">
            Aperçu en direct (mêmes filtres que la liste) — la liste complète remplace cet aperçu à la fin de
            l’actualisation.
          </p>
          <p v-else class="text-muted text-xs">Les fiches s’affichent ici dès qu’Amazon les renvoie…</p>
          <div
            v-if="streamingDisplayItems.length"
            class="grid grid-cols-1 gap-3 md:grid-cols-2 md:gap-4 2xl:grid-cols-3"
          >
            <GoupixDexAmazonInviteCard
              v-for="inv in streamingDisplayItems"
              :key="`stream-${inv.id}`"
              :invite="inv"
              :request-invite-loading="requestInviteLoadingAsin === (inv.asin ?? '').trim().toUpperCase()"
              @request-invite="requestProductInvite"
            />
          </div>
        </div>

        <div
          v-if="!refreshing && !loading && !error && displayItems.length"
          class="grid grid-cols-1 gap-3 md:grid-cols-2 md:gap-4 2xl:grid-cols-3"
        >
          <GoupixDexAmazonInviteCard
            v-for="inv in displayItems"
            :key="inv.id"
            :invite="inv"
            :request-invite-loading="requestInviteLoadingAsin === (inv.asin ?? '').trim().toUpperCase()"
            @request-invite="requestProductInvite"
          />
        </div>

        <div
          v-else-if="!refreshing && !loading && !error"
          class="border-default/60 bg-elevated/20 flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed px-6 py-12 text-center"
        >
          <UIcon name="i-lucide-inbox" class="text-primary size-8" />
          <p class="text-highlighted text-sm font-medium">Aucune invitation à afficher</p>
          <p class="text-muted max-w-md text-xs">
            Ajustez la recherche ou le nombre de pages ci-dessus, puis appuyez sur « Actualiser » pour charger vos
            invitations Amazon.
          </p>
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { ComputedRef } from 'vue'
import type { AmazonConnectionBadge } from '~/utils/amazonConnectionUi'
import { amazonSessionBadge } from '~/utils/amazonConnectionUi'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Invitations Amazon',
  'Produits Pokémon Amazon sur invitation : suivez le statut de chaque demande et lancez une invitation depuis GoupixDex lorsque c’est possible.',
)

const {
  loading,
  refreshing,
  error,
  session,
  refreshedAt,
  searchQuery,
  hideExpired,
  optionalSearch,
  maxPages,
  items,
  statusFilter,
  statusSelectItems,
  displayItems,
  streamingDisplayItems,
  refreshLogLines,
  refreshPhaseHint,
  requestInviteLoadingAsin,
  load,
  refresh,
  requestProductInvite,
} = useAmazonInvitesPage()

/**
 * Navbar badge reflecting Amazon worker session state (loading / error / API-derived).
 */
const connectionBadge: ComputedRef<AmazonConnectionBadge | null> = computed(() => {
  if (loading.value) {
    return { label: 'Vérification…', color: 'neutral' }
  }
  if (error.value && !session.value) {
    return { label: 'Connexion locale indisponible', color: 'error' }
  }
  if (!session.value) {
    return null
  }
  return amazonSessionBadge(session.value)
})

onMounted((): void => {
  void load()
})
</script>
