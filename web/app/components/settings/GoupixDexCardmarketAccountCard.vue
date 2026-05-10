<template>
  <UCard>
    <template #header>
      <div class="space-y-1">
        <div class="flex items-center justify-between gap-3">
          <p class="text-highlighted font-medium">Compte Cardmarket (panier)</p>
          <UBadge :color="badge.color" variant="subtle">
            {{ badge.label }}
          </UBadge>
        </div>
        <p class="text-muted text-sm">
          Un Chromium dédié (même principe que Vinted / Amazon) conserve vos cookies Cardmarket sur cet ordinateur.
          Connectez-vous une seule fois ; vos analyses « panier » utiliseront ensuite cette session (réduit fortement
          les blocages Cloudflare et le rate-limit).
        </p>
      </div>
    </template>

    <div class="space-y-4">
      <UAlert
        v-if="!isDesktopApp"
        color="info"
        variant="subtle"
        icon="i-lucide-monitor-smartphone"
        title="Application bureau"
        description="L’ouverture du navigateur et la détection de session ont lieu dans l’application GoupixDex desktop (worker local)."
      />

      <UAlert
        v-else-if="workerError"
        color="warning"
        variant="subtle"
        icon="i-lucide-unplug"
        title="Worker Cardmarket injoignable"
        description="Démarrez l’application bureau ou vérifiez que le service Cardmarket local écoute bien (port 18770 par défaut)."
      />

      <div v-else-if="session?.state === 'ready'" class="text-muted space-y-1 text-sm">
        <p>
          Session Cardmarket détectée pour <strong>{{ session.username }}</strong
          ><span v-if="session.credit_eur != null"> · crédit {{ formatCredit(session.credit_eur) }}</span
          >.
        </p>
        <p v-if="session.last_seen" class="text-xs">Dernière vérification : {{ formatLastSeen(session.last_seen) }}</p>
      </div>

      <UAlert
        v-else-if="session?.state === 'busy'"
        color="info"
        variant="subtle"
        icon="i-lucide-loader-circle"
        title="Connexion en cours"
        :description="session.message ?? 'Connectez-vous dans la fenêtre Chrome ouverte.'"
      />

      <p v-else-if="session?.state === 'needs_login'" class="text-muted text-sm">
        Aucune session Cardmarket détectée. Cliquez sur « Ouvrir Chrome » et identifiez-vous sur Cardmarket.
      </p>

      <div class="flex flex-wrap items-center gap-2">
        <UButton
          v-if="isDesktopApp && !workerError"
          color="primary"
          icon="i-lucide-chrome"
          :loading="openingBrowser"
          @click="openLoginBrowser"
        >
          {{ session?.state === 'ready' ? 'Ouvrir Chrome (vérifier)' : 'Ouvrir Chrome — connexion Cardmarket' }}
        </UButton>
        <UButton
          v-if="isDesktopApp"
          color="neutral"
          variant="ghost"
          icon="i-lucide-refresh-cw"
          :loading="refreshingState"
          @click="refreshState"
        >
          Actualiser l’état
        </UButton>
        <UButton
          v-if="isDesktopApp && session?.state === 'ready'"
          color="neutral"
          variant="soft"
          icon="i-lucide-log-out"
          :loading="loggingOut"
          @click="logout"
        >
          Oublier la session
        </UButton>
      </div>
    </div>
  </UCard>
</template>

<script setup lang="ts">
import type { Ref } from 'vue'
import type { CardmarketSessionResponse } from '~/types/CardmarketSession'
import { cardmarketSessionBadge } from '~/utils/cardmarketConnectionUi'

const { isDesktopApp } = useDesktopRuntime()
const { fetchSession, openLoginBrowser: postOpenLogin, logout: postLogout } = useCardmarketWorker()
const toast = useToast()

const loading: Ref<boolean> = ref(true)
const refreshingState: Ref<boolean> = ref(false)
const openingBrowser: Ref<boolean> = ref(false)
const loggingOut: Ref<boolean> = ref(false)
const session: Ref<CardmarketSessionResponse | null> = ref(null)
const workerError: Ref<boolean> = ref(false)

let pollHandle: ReturnType<typeof setInterval> | null = null

const badge = computed(() => {
  if (!isDesktopApp.value) {
    return { label: 'Web uniquement', color: 'neutral' as const }
  }
  if (loading.value) {
    return { label: 'Vérification…', color: 'neutral' as const }
  }
  if (workerError.value) {
    return { label: 'Worker indisponible', color: 'error' as const }
  }
  return cardmarketSessionBadge(session.value)
})

function formatCredit(value: number): string {
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(value)
}

function formatLastSeen(iso: string): string {
  try {
    const d = new Date(iso)
    return d.toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return iso
  }
}

async function loadState(): Promise<void> {
  if (!isDesktopApp.value) {
    loading.value = false
    return
  }
  loading.value = true
  workerError.value = false
  try {
    session.value = await fetchSession()
  } catch {
    workerError.value = true
    session.value = null
  } finally {
    loading.value = false
  }
}

async function refreshState(): Promise<void> {
  if (!isDesktopApp.value) {
    return
  }
  refreshingState.value = true
  workerError.value = false
  try {
    session.value = await fetchSession()
  } catch {
    workerError.value = true
    session.value = null
  } finally {
    refreshingState.value = false
  }
}

function startPolling(): void {
  stopPolling()
  if (!isDesktopApp.value) {
    return
  }
  pollHandle = setInterval(() => {
    if (session.value?.state === 'ready' && !session.value?.browser_open) {
      stopPolling()
      return
    }
    void refreshState()
  }, 3000)
}

function stopPolling(): void {
  if (pollHandle) {
    clearInterval(pollHandle)
    pollHandle = null
  }
}

async function openLoginBrowser(): Promise<void> {
  if (!isDesktopApp.value) {
    return
  }
  openingBrowser.value = true
  try {
    await postOpenLogin()
    toast.add({
      title: 'Chrome ouvert',
      description: 'Connectez-vous à Cardmarket dans la fenêtre. La détection est automatique.',
      color: 'success',
    })
    await refreshState()
    startPolling()
  } catch (e: unknown) {
    toast.add({
      title: 'Impossible d’ouvrir Chrome',
      description: apiErrorMessage(e),
      color: 'error',
    })
  } finally {
    openingBrowser.value = false
  }
}

async function logout(): Promise<void> {
  if (!isDesktopApp.value) {
    return
  }
  loggingOut.value = true
  try {
    await postLogout()
    toast.add({
      title: 'Session oubliée',
      description: 'GoupixDex ne mémorise plus votre pseudo Cardmarket. Les cookies restent dans le profil Chrome.',
      color: 'success',
    })
    stopPolling()
    await refreshState()
  } catch (e: unknown) {
    toast.add({
      title: 'Erreur',
      description: apiErrorMessage(e),
      color: 'error',
    })
  } finally {
    loggingOut.value = false
  }
}

onMounted(() => {
  void loadState()
})

onBeforeUnmount(() => {
  stopPolling()
})

watch(isDesktopApp, (desktop) => {
  if (desktop) {
    void loadState()
  } else {
    stopPolling()
    session.value = null
    workerError.value = false
    loading.value = false
  }
})
</script>
