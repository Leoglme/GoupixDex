<script setup lang="ts">
import type { DownloadEvent } from '@tauri-apps/plugin-updater'
import { check } from '@tauri-apps/plugin-updater'
import { relaunch } from '@tauri-apps/plugin-process'

type UpdaterStatus = 'idle' | 'available' | 'downloading' | 'installed' | 'error'

const { isDesktopApp } = useDesktopRuntime()

const visible = ref(false)
const status = ref<UpdaterStatus>('idle')
const currentVersion = ref<string | null>(null)
const nextVersion = ref<string | null>(null)
const errorMessage = ref<string | null>(null)
const pendingUpdate = shallowRef<Awaited<ReturnType<typeof check>>>(null)

const downloadedBytes = ref(0)
const totalBytes = ref<number | null>(null)
const downloadPercent = computed(() => {
  const total = totalBytes.value
  if (total == null || total <= 0) {
    return null
  }
  return Math.min(100, Math.round((100 * downloadedBytes.value) / total))
})

const downloadLabel = computed(() => {
  if (status.value !== 'downloading') {
    return ''
  }
  const pct = downloadPercent.value
  if (pct != null) {
    return `${pct} %`
  }
  if (downloadedBytes.value > 0) {
    const mb = (downloadedBytes.value / (1024 * 1024)).toFixed(1)
    return `${mb} Mo téléchargés`
  }
  return 'Préparation du téléchargement…'
})

const canDismiss = computed(() => status.value === 'available' || status.value === 'error')

const statusTitle = computed(() => {
  if (status.value === 'available') return 'Mise à jour disponible'
  if (status.value === 'downloading') return 'Téléchargement et installation'
  if (status.value === 'installed') return 'Mise à jour installée'
  if (status.value === 'error') return 'Mise à jour impossible'
  return 'Mise à jour'
})

const statusDescription = computed(() => {
  if (status.value === 'available') {
    if (nextVersion.value && currentVersion.value) {
      return `Passez de la version ${currentVersion.value} à ${nextVersion.value} en un clic. L'application se fermera brièvement pour finaliser l'installation.`
    }
    if (nextVersion.value) {
      return `La version ${nextVersion.value} est prête. L'application se fermera brièvement pour finaliser l'installation.`
    }
    return "Une nouvelle version est prête. L'application se fermera brièvement pour finaliser l'installation."
  }
  if (status.value === 'downloading') {
    return "Ne fermez pas GoupixDex pendant cette étape. Une fois terminé, vous pourrez redémarrer l'application pour appliquer la nouvelle version."
  }
  if (status.value === 'installed') {
    return 'Redémarrez GoupixDex pour charger la nouvelle version. Vos données et votre session locale sont conservées.'
  }
  if (status.value === 'error') {
    return errorMessage.value || 'Une erreur est survenue pendant la mise à jour.'
  }
  return ''
})

function resetDownloadProgress() {
  downloadedBytes.value = 0
  totalBytes.value = null
}

function onDownloadEvent(event: DownloadEvent) {
  if (event.event === 'Started') {
    const len = event.data.contentLength
    totalBytes.value = len != null && len > 0 ? len : null
    downloadedBytes.value = 0
  } else if (event.event === 'Progress') {
    downloadedBytes.value += event.data.chunkLength
  }
}

function closePanel() {
  if (!canDismiss.value) {
    return
  }
  visible.value = false
}

async function installUpdate() {
  if (!pendingUpdate.value) {
    return
  }

  try {
    status.value = 'downloading'
    errorMessage.value = null
    resetDownloadProgress()
    await pendingUpdate.value.downloadAndInstall(onDownloadEvent)
    status.value = 'installed'
  } catch (error) {
    status.value = 'error'
    errorMessage.value = error instanceof Error ? error.message : "Échec du téléchargement ou de l'installation."
  }
}

async function restartApp() {
  try {
    await relaunch()
  } catch (e) {
    console.error('[Updater] relaunch() a échoué, rechargement WebView en secours :', e)
    window.location.reload()
  }
}

async function checkForUpdate() {
  if (!import.meta.client || !isDesktopApp.value) {
    return
  }

  if (window.sessionStorage.getItem('goupix-updater-checked') === '1') {
    return
  }
  window.sessionStorage.setItem('goupix-updater-checked', '1')

  errorMessage.value = null
  resetDownloadProgress()

  try {
    const update = await check()
    pendingUpdate.value = update

    if (!update) {
      status.value = 'idle'
      return
    }

    currentVersion.value = update.currentVersion || null
    nextVersion.value = update.version || null
    status.value = 'available'
    visible.value = true
  } catch (error) {
    console.error('[Updater] Vérification silencieuse échouée :', error)
    status.value = 'idle'
    pendingUpdate.value = null
  }
}

onMounted(() => {
  checkForUpdate()
})
</script>

<template>
  <Transition
    enter-active-class="transition duration-300 ease-out"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition duration-200 ease-in"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="visible"
      class="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4 backdrop-blur-md"
      @click.self="closePanel"
    >
      <UCard
        class="relative w-full max-w-lg overflow-hidden border border-default/80 shadow-2xl shadow-black/25 ring-1 ring-primary/15"
        :ui="{ body: 'p-0', ring: '', rounded: 'rounded-2xl' }"
      >
        <div
          class="absolute inset-0 bg-gradient-to-br from-primary/[0.07] via-transparent to-elevated/80 pointer-events-none"
          aria-hidden="true"
        />
        <div class="absolute -right-20 -top-20 size-56 rounded-full bg-primary/10 blur-3xl pointer-events-none" />
        <div class="absolute -bottom-24 -left-16 size-48 rounded-full bg-primary/5 blur-3xl pointer-events-none" />

        <div class="relative space-y-6 p-6 sm:p-8">
          <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div class="flex items-start gap-4 min-w-0">
              <div
                class="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-primary/15 ring-1 ring-primary/25 shadow-inner"
              >
                <UIcon
                  :name="status === 'installed' ? 'i-lucide-sparkles' : 'i-lucide-download-cloud'"
                  class="size-6 text-primary"
                />
              </div>
              <div class="min-w-0 space-y-2">
                <p class="text-[11px] font-semibold uppercase tracking-[0.12em] text-primary">
                  Mise à jour · Desktop
                </p>
                <h2 class="text-xl font-semibold tracking-tight text-highlighted sm:text-2xl">
                  {{ statusTitle }}
                </h2>
                <p class="text-sm leading-relaxed text-muted">
                  {{ statusDescription }}
                </p>
              </div>
            </div>

            <div
              v-if="currentVersion || nextVersion"
              class="flex shrink-0 flex-wrap items-center gap-2 sm:flex-col sm:items-end"
            >
              <UBadge
                v-if="currentVersion"
                color="neutral"
                variant="subtle"
                size="md"
                class="font-mono text-xs"
              >
                v{{ currentVersion }}
              </UBadge>
              <UIcon
                v-if="currentVersion && nextVersion"
                name="i-lucide-arrow-right"
                class="size-4 text-muted sm:rotate-90"
              />
              <UBadge
                v-if="nextVersion"
                color="primary"
                variant="subtle"
                size="md"
                class="font-mono text-xs ring-1 ring-primary/30"
              >
                v{{ nextVersion }}
              </UBadge>
            </div>
          </div>

          <div v-if="status === 'downloading'" class="space-y-3">
            <div class="flex items-center justify-between gap-3 text-xs text-muted">
              <span class="tabular-nums font-medium text-highlighted">{{ downloadLabel }}</span>
              <span v-if="totalBytes && totalBytes > 0" class="tabular-nums">
                {{ (downloadedBytes / (1024 * 1024)).toFixed(1) }} / {{ (totalBytes / (1024 * 1024)).toFixed(1) }} Mo
              </span>
            </div>
            <UProgress
              v-if="downloadPercent != null"
              :model-value="downloadPercent"
              :max="100"
              status
              size="md"
              class="w-full"
            />
            <UProgress
              v-else
              animation="carousel"
              size="md"
              class="w-full"
            />
          </div>

          <UAlert
            v-if="status === 'error' && errorMessage"
            color="error"
            variant="subtle"
            icon="i-lucide-alert-triangle"
            :description="errorMessage"
          />

          <div
            class="flex flex-wrap items-center justify-end gap-3 border-t border-default/50 pt-5"
          >
            <UButton
              v-if="canDismiss"
              color="neutral"
              variant="ghost"
              icon="i-lucide-x"
              @click="closePanel"
            >
              Plus tard
            </UButton>

            <UButton
              v-if="status === 'available'"
              color="primary"
              size="lg"
              icon="i-lucide-download"
              class="shadow-lg shadow-primary/20"
              @click="installUpdate"
            >
              Mettre à jour maintenant
            </UButton>

            <UButton
              v-if="status === 'installed'"
              color="primary"
              size="lg"
              icon="i-lucide-refresh-ccw"
              class="shadow-lg shadow-primary/20"
              @click="restartApp"
            >
              Redémarrer GoupixDex
            </UButton>

            <UButton
              v-if="status === 'error'"
              color="neutral"
              variant="soft"
              icon="i-lucide-refresh-cw"
              @click="installUpdate"
            >
              Réessayer
            </UButton>
          </div>
        </div>
      </UCard>
    </div>
  </Transition>
</template>
