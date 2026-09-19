<template>
  <UDashboardPanel id="amazon-invites">
    <template #header>
      <UDashboardNavbar>
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #title>
          <span class="app-label flex items-center gap-1.5 !text-[0.65rem]">
            <UIcon name="i-lucide-flame" class="h-3 w-3 text-(--app-accent)" />
            Achats
          </span>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="w-full space-y-3 px-2 py-2.5 sm:space-y-4 sm:px-4 sm:py-4">
        <GoupixDexPageHeader
          title="Invitations Amazon"
          description="Produits Pokémon vendus sur invitation : statut de chaque demande, et bouton pour la poser sans quitter GoupixDex."
        >
          <template #actions>
            <UBadge v-if="connectionBadge" :color="connectionBadge.color" variant="subtle" class="shrink-0">
              {{ connectionBadge.label }}
            </UBadge>
          </template>
        </GoupixDexPageHeader>

        <GoupixDexDesktopOnlyNotice
          v-if="!isDesktopApp"
          feature-label="Invitations Amazon"
          reason="La récupération des invitations pilote une fenêtre Chrome locale (worker Amazon) : elle n'existe que dans l'application desktop."
        />

        <template v-else>
          <GoupixDexAmazonSessionBanner :session="session" :loading="loading" />

          <UCard>
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

          <GoupixDexAmazonRefreshProgress
            v-if="refreshing"
            :phase-hint="refreshPhaseHint"
            :log-lines="refreshLogLines"
          />

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
        </template>
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

const { isDesktopApp } = useDesktopRuntime()

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
  if (isDesktopApp.value) {
    load()
  }
})
</script>
