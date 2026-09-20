<template>
  <UCard v-if="enabled" :ui="cardUi" :class="embedded ? '' : 'border-[#FF6E14]/20'">
    <template v-if="!embedded" #header>
      <div class="space-y-1">
        <div class="flex items-center justify-between gap-3">
          <div class="flex min-w-0 items-center gap-2">
            <GoupixDexLeboncoinLogo class="h-5 w-auto shrink-0" aria-hidden="true" />
            <p class="text-highlighted font-medium">Connexion Leboncoin</p>
          </div>
          <UBadge :color="badge.color" variant="subtle" class="shrink-0">
            {{ badge.label }}
          </UBadge>
        </div>
        <p class="text-muted text-sm">
          Même principe que Cardmarket : un profil Chromium sur cet ordinateur conserve vos cookies. Connectez-vous une
          fois pour publier vos annonces.
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
        description="L’ouverture du navigateur et la détection de session ont lieu dans l’application GoupixDex desktop."
      />

      <UAlert
        v-else-if="workerError"
        color="warning"
        variant="subtle"
        icon="i-lucide-unplug"
        title="Worker Leboncoin injoignable"
        description="Vérifiez que le service local écoute (port 18769) ou redémarrez l’application."
      />

      <p v-else-if="session?.state === 'ready'" class="text-muted text-sm">
        Session Leboncoin détectée. Vous pouvez publier depuis <strong>Mes articles</strong>.
      </p>

      <UAlert
        v-else-if="session?.state === 'busy' || session?.browser_open"
        color="info"
        variant="subtle"
        icon="i-lucide-chrome"
        title="Chrome ouvert"
        :description="
          session?.message ||
          'Connectez-vous sur leboncoin.fr. GoupixDex ferme Chrome automatiquement une fois la session détectée.'
        "
      />

      <UAlert
        v-else-if="session?.state === 'unreadable'"
        color="warning"
        variant="subtle"
        icon="i-lucide-lock"
        title="Profil verrouillé"
        description="Fermez toutes les fenêtres Chrome Leboncoin, puis actualisez l’état."
      />

      <p v-else class="text-muted text-sm">
        Aucune session détectée. Ouvrez Chrome et identifiez-vous sur leboncoin.fr.
      </p>

      <div class="flex flex-wrap items-center gap-2">
        <UButton
          v-if="isDesktopApp && !workerError"
          color="primary"
          icon="i-lucide-chrome"
          :loading="opening"
          @click="onOpenChrome"
        >
          {{ session?.state === 'ready' ? 'Ouvrir Chrome (vérifier)' : 'Ouvrir Chrome — connexion Leboncoin' }}
        </UButton>
        <UButton
          v-if="isDesktopApp"
          color="neutral"
          variant="ghost"
          icon="i-lucide-refresh-cw"
          :loading="loading"
          @click="refresh"
        >
          Actualiser l’état
        </UButton>
      </div>
    </div>
  </UCard>
</template>

<script setup lang="ts">
import type { LeboncoinSessionResponse } from '~/composables/useLeboncoinWorker'
import { leboncoinSessionBadge } from '~/utils/leboncoinConnectionUi'

const props = withDefaults(
  defineProps<{
    enabled: boolean
    embedded?: boolean
  }>(),
  { embedded: false },
)

const cardUi = computed(() =>
  props.embedded
    ? {
        root: 'ring-0 shadow-none rounded-none bg-transparent',
        header: 'hidden',
        body: 'p-4 sm:p-5',
      }
    : undefined,
)

const { isDesktopApp } = useDesktopRuntime()
const { fetchSession, openLoginBrowser } = useLeboncoinWorker()
const toast = useToast()

const loading = ref(false)
const opening = ref(false)
const workerError = ref(false)
const session = ref<LeboncoinSessionResponse | null>(null)

let pollHandle: ReturnType<typeof setInterval> | null = null

const badge = computed(() => leboncoinSessionBadge(session.value))

async function refresh() {
  if (!import.meta.client || !isDesktopApp.value) {
    return
  }
  loading.value = true
  workerError.value = false
  try {
    session.value = await fetchSession()
    if (session.value?.state === 'ready' && !session.value.browser_open) {
      stopPolling()
    }
  } catch (e) {
    workerError.value = true
    toast.add({ title: 'Worker Leboncoin', description: apiErrorMessage(e), color: 'error' })
  } finally {
    loading.value = false
  }
}

function startPolling() {
  stopPolling()
  if (!isDesktopApp.value) {
    return
  }
  pollHandle = setInterval(() => {
    void refresh()
  }, 3000)
}

function stopPolling() {
  if (pollHandle) {
    clearInterval(pollHandle)
    pollHandle = null
  }
}

async function onOpenChrome() {
  opening.value = true
  try {
    await openLoginBrowser()
    toast.add({
      title: 'Chrome ouvert',
      description: 'Connectez-vous sur Leboncoin. La détection et la fermeture de Chrome sont automatiques.',
      color: 'success',
    })
    await refresh()
    startPolling()
  } catch (e) {
    toast.add({ title: 'Impossible d’ouvrir Chrome', description: apiErrorMessage(e), color: 'error' })
  } finally {
    opening.value = false
  }
}

watch(
  () => props.enabled,
  (on) => {
    if (on) {
      void refresh()
    } else {
      stopPolling()
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  stopPolling()
})
</script>
