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
      <div class="app-dashboard-page w-full">
        <GoupixDexPageHeader
          title="Invitations Amazon"
          description="Produits Pokémon vendus sur invitation : statut de chaque demande, et bouton pour la poser sans quitter GoupixDex."
        >
          <template #actions>
            <div class="flex flex-wrap items-center justify-end gap-2">
              <UButton
                color="neutral"
                variant="outline"
                icon="i-lucide-users"
                size="sm"
                @click="accountsDrawerOpen = true"
              >
                Comptes
              </UButton>
              <UBadge
                v-if="connectionBadge"
                :color="connectionBadge.color"
                variant="subtle"
                class="inline-flex shrink-0 items-center gap-1.5"
              >
                <UIcon name="i-simple-icons-amazon" class="size-3.5 shrink-0" aria-hidden="true" />
                <span>{{ connectionBadge.label }}</span>
              </UBadge>
            </div>
          </template>
        </GoupixDexPageHeader>

        <GoupixDexDesktopOnlyNotice
          v-if="!isDesktopApp"
          feature-label="Invitations Amazon"
          reason="La récupération des invitations pilote une fenêtre Chrome locale (worker Amazon) : elle n'existe que dans l'application desktop."
        />

        <template v-else>
          <UCard>
            <template #header>
              <p class="text-highlighted font-medium">Invitations</p>
            </template>

            <GoupixDexAmazonInvitesToolbar
              v-model:max-items="maxItems"
              v-model:search-query="searchQuery"
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

          <div v-if="accountSelectItems.length && !refreshing" class="flex flex-wrap items-center gap-2">
            <USelect
              :model-value="selectedAccountId"
              :items="accountSelectItems"
              value-key="value"
              class="w-full max-w-md min-w-0"
              :disabled="accountSwitching || refreshing || loading"
              :loading="accountSwitching"
              placeholder="Compte Amazon"
              @update:model-value="onAccountChange"
            />
            <p v-if="accountBackgroundSync" class="text-muted text-xs">
              Sync Amazon en arrière-plan (liste déjà à jour).
            </p>
          </div>

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
            v-else-if="!refreshing && !loading && !error && items.length"
            class="border-default/60 bg-elevated/20 flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed px-6 py-12 text-center"
          >
            <UIcon name="i-lucide-filter" class="text-primary size-8" />
            <p class="text-highlighted text-sm font-medium">
              {{ items.length }} invitation{{ items.length > 1 ? 's' : '' }} trouvée{{ items.length > 1 ? 's' : '' }},
              masquée{{ items.length > 1 ? 's' : '' }} par le filtre « {{ activeStatusFilterLabel }} »
            </p>
            <p class="text-muted max-w-md text-xs">
              Choisissez « Tous les statuts » dans le filtre ci-dessus pour voir la liste récupérée.
            </p>
          </div>

          <div
            v-else-if="!refreshing && !loading && !error"
            class="border-default/60 bg-elevated/20 flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed px-6 py-12 text-center"
          >
            <UIcon name="i-lucide-inbox" class="text-primary size-8" />
            <p class="text-highlighted text-sm font-medium">Aucune invitation à afficher</p>
            <p class="text-muted max-w-md text-xs">
              Ajustez la recherche ou le nombre de produits ci-dessus, puis appuyez sur « Actualiser » pour charger vos
              invitations Amazon.
            </p>
          </div>
        </template>
      </div>

      <GoupixDexAmazonAccountsDrawer v-model:open="accountsDrawerOpen" @changed="onVaultChanged" />
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { ComputedRef } from 'vue'
import type { AmazonConnectionBadge } from '~/utils/amazonConnectionUi'
import type { AmazonStatusFilter } from '~/types/amazonInvites'
import { amazonSessionBadge } from '~/utils/amazonConnectionUi'

const STATUS_FILTER_LABELS: Record<AmazonStatusFilter, string> = {
  all: 'Tous les statuts',
  accepted: 'Commandable',
  requested: 'Invitation demandée',
  not_requested: 'Non demandée',
}

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Invitations Amazon',
  'Produits Pokémon Amazon sur invitation : suivez le statut de chaque demande et lancez une invitation depuis GoupixDex lorsque c’est possible.',
)

const { isDesktopApp } = useDesktopRuntime()
const route = useRoute()
const router = useRouter()

const accountsDrawerOpen = ref(false)

const {
  loading,
  refreshing,
  error,
  session,
  refreshedAt: _refreshedAt,
  searchQuery,
  maxItems,
  items,
  statusFilter,
  statusSelectItems,
  displayItems,
  streamingDisplayItems,
  refreshLogLines,
  refreshPhaseHint,
  requestInviteLoadingAsin,
  accountSelectItems,
  vaultAccountCount,
  selectedAccountId,
  accountSwitching,
  accountBackgroundSync,
  load,
  refresh,
  requestProductInvite,
  switchActiveAccount,
} = useAmazonInvitesPage()

const activeStatusFilterLabel: ComputedRef<string> = computed(() => STATUS_FILTER_LABELS[statusFilter.value])

async function onAccountChange(id: number | null | undefined): Promise<void> {
  if (id == null) {
    return
  }
  await switchActiveAccount(id)
}

async function onVaultChanged(): Promise<void> {
  await load()
}

function maybeOpenAccountsFromQuery(): void {
  if (route.query.accounts === '1' || route.query.accounts === 'open') {
    accountsDrawerOpen.value = true
    void router.replace({ path: route.path, query: {} })
  }
}

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
  const base = amazonSessionBadge(session.value)
  const n = vaultAccountCount.value
  if (n > 0 && base.color === 'success') {
    return {
      ...base,
      label: `${base.label} · ${n} compte${n > 1 ? 's' : ''}`,
    }
  }
  if (n > 0 && session.value.state === 'needs_login') {
    return {
      ...base,
      label: `${base.label} · ${n} en coffre`,
    }
  }
  return base
})

onMounted((): void => {
  maybeOpenAccountsFromQuery()
  if (isDesktopApp.value) {
    void load()
  }
})

watch(
  () => route.query.accounts,
  () => maybeOpenAccountsFromQuery(),
)
</script>
