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
        class="border-default/80 ring-primary/15 relative w-full max-w-lg overflow-hidden border shadow-2xl ring-1 shadow-black/25"
        :ui="{ root: 'rounded-2xl ring-0', body: 'p-0' }"
      >
        <div
          class="from-primary/[0.07] to-elevated/80 pointer-events-none absolute inset-0 bg-gradient-to-br via-transparent"
          aria-hidden="true"
        />
        <div class="bg-primary/10 pointer-events-none absolute -top-20 -right-20 size-56 rounded-full blur-3xl" />
        <div class="bg-primary/5 pointer-events-none absolute -bottom-24 -left-16 size-48 rounded-full blur-3xl" />

        <div class="relative space-y-6 p-6 sm:p-8">
          <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div class="flex min-w-0 items-start gap-4">
              <div
                class="bg-primary/15 ring-primary/25 flex size-12 shrink-0 items-center justify-center rounded-2xl shadow-inner ring-1"
              >
                <UIcon
                  :name="status === 'installed' ? 'i-lucide-sparkles' : 'i-lucide-download-cloud'"
                  class="text-primary size-6"
                />
              </div>
              <div class="min-w-0 space-y-2">
                <p class="text-primary text-[11px] font-semibold tracking-[0.12em] uppercase">Mise à jour · Desktop</p>
                <h2 class="text-highlighted text-xl font-semibold tracking-tight sm:text-2xl">
                  {{ statusTitle }}
                </h2>
                <p class="text-muted text-sm leading-relaxed">
                  {{ statusDescription }}
                </p>
              </div>
            </div>

            <div
              v-if="currentVersion || nextVersion"
              class="flex shrink-0 flex-wrap items-center gap-2 sm:flex-col sm:items-end"
            >
              <UBadge v-if="currentVersion" color="neutral" variant="subtle" size="md" class="font-mono text-xs">
                v{{ currentVersion }}
              </UBadge>
              <UIcon
                v-if="currentVersion && nextVersion"
                name="i-lucide-arrow-right"
                class="text-muted size-4 sm:rotate-90"
              />
              <UBadge
                v-if="nextVersion"
                color="primary"
                variant="subtle"
                size="md"
                class="ring-primary/30 font-mono text-xs ring-1"
              >
                v{{ nextVersion }}
              </UBadge>
            </div>
          </div>

          <div v-if="status === 'downloading'" class="space-y-3">
            <div class="text-muted flex items-center justify-between gap-3 text-xs">
              <span class="text-highlighted font-medium tabular-nums">{{ downloadLabel }}</span>
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
            <UProgress v-else animation="carousel" size="md" class="w-full" />
          </div>

          <UAlert
            v-if="status === 'error' && errorMessage"
            color="error"
            variant="subtle"
            icon="i-lucide-alert-triangle"
            :description="errorMessage"
          />

          <div class="border-default/50 flex flex-wrap items-center justify-end gap-3 border-t pt-5">
            <UButton v-if="canDismiss" color="neutral" variant="ghost" icon="i-lucide-x" @click="closePanel">
              Plus tard
            </UButton>

            <UButton
              v-if="status === 'available'"
              color="primary"
              size="lg"
              icon="i-lucide-download"
              class="shadow-primary/20 shadow-lg"
              @click="installUpdate"
            >
              Mettre à jour maintenant
            </UButton>

            <UButton
              v-if="status === 'installed'"
              color="primary"
              size="lg"
              icon="i-lucide-refresh-ccw"
              class="shadow-primary/20 shadow-lg"
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

<script setup lang="ts">
import type { ComputedRef, Ref } from 'vue'
import type { DownloadEvent, Update } from '@tauri-apps/plugin-updater'
import type { GoupixDexUpdaterStatus } from '~/types/GoupixDexDesktopUpdaterPanel'
import { check } from '@tauri-apps/plugin-updater'
import { relaunch } from '@tauri-apps/plugin-process'
import { invoke } from '@tauri-apps/api/core'

/* Composables */
const desktopRuntime = useDesktopRuntime()
const isDesktopApp = desktopRuntime.isDesktopApp

/* Refs */
const visible: Ref<boolean> = ref(false)
const status: Ref<GoupixDexUpdaterStatus> = ref('idle')
const currentVersion: Ref<string | null> = ref(null)
const nextVersion: Ref<string | null> = ref(null)
const errorMessage: Ref<string | null> = ref(null)
const pendingUpdate: Ref<Update | null> = shallowRef(null)

const downloadedBytes: Ref<number> = ref(0)
const totalBytes: Ref<number | null> = ref(null)

/* Computed */
const downloadPercent: ComputedRef<number | null> = computed((): number | null => {
  const total: number | null = totalBytes.value
  if (total == null || total <= 0) {
    return null
  }
  return Math.min(100, Math.round((100 * downloadedBytes.value) / total))
})

const downloadLabel: ComputedRef<string> = computed((): string => {
  if (status.value !== 'downloading') {
    return ''
  }
  const pct: number | null = downloadPercent.value
  if (pct != null) {
    return `${pct} %`
  }
  if (downloadedBytes.value > 0) {
    const mb: string = (downloadedBytes.value / (1024 * 1024)).toFixed(1)
    return `${mb} Mo téléchargés`
  }
  return 'Préparation du téléchargement…'
})

const canDismiss: ComputedRef<boolean> = computed(
  (): boolean => status.value === 'available' || status.value === 'error',
)

const statusTitle: ComputedRef<string> = computed((): string => {
  if (status.value === 'available') return 'Mise à jour disponible'
  if (status.value === 'downloading') return 'Téléchargement et installation'
  if (status.value === 'installed') return 'Mise à jour installée'
  if (status.value === 'error') return 'Mise à jour impossible'
  return 'Mise à jour'
})

const statusDescription: ComputedRef<string> = computed((): string => {
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

/* Functions */
/**
 * Reset download progress metrics.
 * @returns {void} Nothing.
 */
function resetDownloadProgress(): void {
  downloadedBytes.value = 0
  totalBytes.value = null
}

/**
 * Update progress metrics from Tauri updater events.
 * @param {DownloadEvent} event - Updater download event.
 * @returns {void} Nothing.
 */
function onDownloadEvent(event: DownloadEvent): void {
  if (event.event === 'Started') {
    const len: number | undefined = event.data.contentLength
    totalBytes.value = len != null && len > 0 ? len : null
    downloadedBytes.value = 0
  } else if (event.event === 'Progress') {
    downloadedBytes.value += event.data.chunkLength
  }
}

/**
 * Close the panel if dismiss is allowed.
 * @returns {void} Nothing.
 */
function closePanel(): void {
  if (!canDismiss.value) {
    return
  }
  visible.value = false
}

/**
 * Download and install the pending update.
 * @returns {Promise<void>} Resolves when install finished (or failed).
 */
async function installUpdate(): Promise<void> {
  if (!pendingUpdate.value) {
    return
  }

  try {
    status.value = 'downloading'
    errorMessage.value = null
    resetDownloadProgress()

    // On Windows, the NSIS installer overwrites `goupix-vinted-worker.exe`:
    // the sidecar (and its Chromium children spawned by nodriver) must be
    // killed BEFORE, otherwise the install fails with "Error opening file for
    // writing". The Rust side runs a `taskkill /F /T` on the whole tree.
    try {
      await invoke('stop_local_worker')
    } catch (killError) {
      console.warn('[Updater] stop_local_worker failed, proceeding with install anyway:', killError)
    }
    // Give Windows a moment to release handles on the .exe and its DLLs
    // before NSIS starts extracting.
    await new Promise<void>((resolve: () => void): void => {
      setTimeout(resolve, 600)
    })

    await pendingUpdate.value.downloadAndInstall(onDownloadEvent)
    status.value = 'installed'
  } catch (error) {
    status.value = 'error'
    errorMessage.value = error instanceof Error ? error.message : "Échec du téléchargement ou de l'installation."
  }
}

/**
 * Restart the desktop app (best-effort).
 * @returns {Promise<void>} Resolves when restart has been triggered.
 */
async function restartApp(): Promise<void> {
  try {
    await relaunch()
  } catch (e) {
    console.error('[Updater] relaunch() a échoué, rechargement WebView en secours :', e)
    window.location.reload()
  }
}

/**
 * Check for updates once per session and show the panel when available.
 * @returns {Promise<void>} Resolves when check is complete.
 */
async function checkForUpdate(): Promise<void> {
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
    const update: Update | null = await check()
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

/* Lifecycle */
onMounted((): void => {
  void checkForUpdate()
})
</script>
