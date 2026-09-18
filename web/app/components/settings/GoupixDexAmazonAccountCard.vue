<template>
  <UCard>
    <template #header>
      <div class="space-y-1">
        <div class="flex items-center justify-between gap-3">
          <p class="text-highlighted font-medium">Compte Amazon (invitations)</p>
          <UBadge :color="badge.color" variant="subtle">
            {{ badge.label }}
          </UBadge>
        </div>
        <p class="text-muted text-sm">
          Un Chromium dédié (même principe que l’automation Vinted) conserve vos cookies Amazon sur cet ordinateur.
          Ouvrez la fenêtre de connexion et identifiez-vous sur Amazon.fr — l’état ci-dessous se met à jour tout seul.
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
        title="Worker Amazon injoignable"
        :description="workerError"
      />

      <UAlert
        v-else-if="waitingLogin"
        color="info"
        variant="subtle"
        icon="i-lucide-loader-circle"
        title="En attente de votre connexion Amazon…"
        description="Connectez-vous dans la fenêtre Chrome ouverte. Dès que la session est détectée, elle est enregistrée et la fenêtre se ferme toute seule."
      />

      <p v-else-if="!loading && session?.state === 'ready'" class="text-muted text-sm">
        Session Amazon détectée sur ce profil Chromium. Vous pouvez consulter les invitations produits dans le menu.
      </p>

      <p v-else-if="!loading && session?.message" class="text-muted text-sm">
        {{ session.message }}
      </p>

      <div class="flex flex-wrap items-center gap-2">
        <UButton
          v-if="isDesktopApp && !workerError"
          color="primary"
          icon="i-lucide-chrome"
          :loading="openingBrowser"
          :disabled="waitingLogin"
          @click="openLoginBrowser"
        >
          Ouvrir Chrome — connexion Amazon
        </UButton>
        <UButton
          v-if="isDesktopApp && waitingLogin"
          color="neutral"
          variant="subtle"
          icon="i-lucide-x"
          @click="stopWaitingAndClose"
        >
          Fermer Chrome
        </UButton>
        <UButton
          v-if="isDesktopApp && !waitingLogin"
          color="neutral"
          variant="ghost"
          icon="i-lucide-refresh-cw"
          :loading="refreshingState"
          @click="refreshState"
        >
          Actualiser l’état
        </UButton>
      </div>
    </div>
  </UCard>
</template>

<script setup lang="ts">
import type { Ref } from 'vue'
import type { AmazonSessionResponse } from '~/types/amazonInvites'
import { amazonSessionBadge } from '~/utils/amazonConnectionUi'

const { isDesktopApp } = useDesktopRuntime()
const { fetchSession, openLoginBrowser: postOpenLogin, closeLoginBrowser } = useAmazonWorker()
const toast = useToast()

const loading: Ref<boolean> = ref(true)
const refreshingState: Ref<boolean> = ref(false)
const openingBrowser: Ref<boolean> = ref(false)
/** True while the login window is open and we poll the session automatically. */
const waitingLogin: Ref<boolean> = ref(false)
const session: Ref<AmazonSessionResponse | null> = ref(null)
/** Human-readable reason when the local worker cannot be reached. */
const workerError: Ref<string | null> = ref(null)

/** Poll cadence / lifetime while the user signs in (3 s × 60 = 3 minutes). */
const LOGIN_POLL_INTERVAL_MS = 3_000
const LOGIN_POLL_MAX_TRIES = 60
let loginPollTimer: ReturnType<typeof setInterval> | null = null
let loginPollTries = 0

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
  if (waitingLogin.value) {
    return { label: 'En attente de connexion…', color: 'warning' as const }
  }
  return amazonSessionBadge(session.value)
})

/**
 * Fetch `/amazon/session` and update the card state.
 * @param spinner - Which spinner flag to drive (`load` on mount, `refresh` on user click).
 * @returns The fresh session payload, or `null` when the worker is unreachable.
 */
async function fetchState(spinner: 'load' | 'refresh' | 'none' = 'none'): Promise<AmazonSessionResponse | null> {
  if (!isDesktopApp.value) {
    loading.value = false
    return null
  }
  if (spinner === 'load') {
    loading.value = true
  } else if (spinner === 'refresh') {
    refreshingState.value = true
  }
  try {
    const fresh = await fetchSession()
    session.value = fresh
    workerError.value = null
    return fresh
  } catch (e: unknown) {
    workerError.value = apiErrorMessage(e)
    session.value = null
    return null
  } finally {
    loading.value = false
    refreshingState.value = false
  }
}

/**
 * Manual refresh (kept for reassurance; the login flow polls automatically).
 */
async function refreshState(): Promise<void> {
  await fetchState('refresh')
}

/**
 * Stop the login polling loop.
 */
function stopLoginPolling(): void {
  waitingLogin.value = false
  loginPollTries = 0
  if (loginPollTimer !== null) {
    clearInterval(loginPollTimer)
    loginPollTimer = null
  }
}

/**
 * Poll the session while the Chrome window is open; on success, persist the
 * cookies by closing the window and confirm with a toast.
 */
function startLoginPolling(): void {
  stopLoginPolling()
  waitingLogin.value = true
  loginPollTimer = setInterval(async () => {
    loginPollTries += 1
    const fresh = await fetchState()
    if (fresh?.state === 'ready') {
      stopLoginPolling()
      try {
        await closeLoginBrowser()
      } catch {
        /* the profile already holds the cookies; closing is best-effort */
      }
      await fetchState()
      toast.add({
        title: 'Compte Amazon connecté',
        description: 'Session enregistrée — la fenêtre Chrome a été fermée.',
        color: 'success',
      })
      return
    }
    if (loginPollTries >= LOGIN_POLL_MAX_TRIES || workerError.value) {
      stopLoginPolling()
    }
  }, LOGIN_POLL_INTERVAL_MS)
}

/**
 * Cancel the wait: close the worker's Chrome window and re-check once.
 */
async function stopWaitingAndClose(): Promise<void> {
  stopLoginPolling()
  try {
    await closeLoginBrowser()
  } catch (e: unknown) {
    toast.add({ title: 'Fermeture impossible', description: apiErrorMessage(e), color: 'warning' })
  }
  await fetchState('refresh')
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
      description: 'Connectez-vous à Amazon dans la fenêtre — l’état se mettra à jour automatiquement.',
      color: 'success',
    })
    startLoginPolling()
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

onMounted(() => {
  void fetchState('load')
})

onBeforeUnmount(() => {
  stopLoginPolling()
})

watch(isDesktopApp, (desktop) => {
  if (desktop) {
    void fetchState('load')
  } else {
    stopLoginPolling()
    session.value = null
    workerError.value = null
    loading.value = false
  }
})
</script>
