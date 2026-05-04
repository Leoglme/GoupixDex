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
          Ouvrez la fenêtre de connexion, identifiez-vous sur Amazon.fr, puis actualisez l’état ci-dessous.
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
        description="Démarrez l’application bureau ou vérifiez que le service Amazon local écoute bien (port configuré dans la doc)."
      />

      <p v-else-if="!loading && session?.state === 'ready'" class="text-muted text-sm">
        Session Amazon détectée sur ce profil Chromium. Vous pouvez consulter les invitations produits dans le menu.
      </p>

      <div class="flex flex-wrap items-center gap-2">
        <UButton
          v-if="isDesktopApp && !workerError"
          color="primary"
          icon="i-lucide-chrome"
          :loading="openingBrowser"
          @click="openLoginBrowser"
        >
          Ouvrir Chrome — connexion Amazon
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
      </div>
    </div>
  </UCard>
</template>

<script setup lang="ts">
import type { Ref } from 'vue'
import type { AmazonSessionResponse } from '~/types/amazonInvites'
import { amazonSessionBadge } from '~/utils/amazonConnectionUi'

const { isDesktopApp } = useDesktopRuntime()
const { fetchSession, openLoginBrowser: postOpenLogin } = useAmazonWorker()
const toast = useToast()

const loading: Ref<boolean> = ref(true)
const refreshingState: Ref<boolean> = ref(false)
const openingBrowser: Ref<boolean> = ref(false)
const session: Ref<AmazonSessionResponse | null> = ref(null)
const workerError: Ref<boolean> = ref(false)

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
  return amazonSessionBadge(session.value)
})

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

async function openLoginBrowser(): Promise<void> {
  if (!isDesktopApp.value) {
    return
  }
  openingBrowser.value = true
  try {
    await postOpenLogin()
    toast.add({
      title: 'Chrome ouvert',
      description: 'Connectez-vous à Amazon dans la fenêtre, puis appuyez sur « Actualiser l’état ».',
      color: 'success',
    })
    await refreshState()
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
  void loadState()
})

watch(isDesktopApp, (desktop) => {
  if (desktop) {
    void loadState()
  } else {
    session.value = null
    workerError.value = false
    loading.value = false
  }
})
</script>
