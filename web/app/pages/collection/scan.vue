<template>
  <UDashboardPanel id="collection-scan">
    <template #header>
      <UDashboardNavbar title="Scanner mes cartes">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton to="/collection" color="neutral" variant="ghost" icon="i-lucide-album"> Ma collection </UButton>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="w-full space-y-4 px-3 py-4 sm:space-y-5 sm:px-5 sm:py-5">
        <!-- Hero / mode d'emploi -->
        <div
          class="border-default from-primary/10 via-elevated/60 to-primary/5 relative overflow-hidden rounded-2xl border bg-gradient-to-br px-3 py-3 sm:px-5 sm:py-4"
        >
          <div class="flex flex-col gap-2">
            <p class="text-primary text-xs font-medium tracking-wide uppercase">Scan en direct</p>
            <h1 class="text-highlighted text-base font-semibold sm:text-lg">
              Photographiez vos cartes à la chaîne — elles arrivent dans votre collection en temps réel.
            </h1>
            <p class="text-muted text-sm">
              Scannez vos cartes à la chaîne&nbsp;: la langue (FR / JP…) est reconnue automatiquement. En HTTPS, le mode
              caisse capture chaque carte tenue immobile sans rien toucher.
            </p>
          </div>
        </div>

        <!-- Caméra live + auto-capture (téléphone et desktop) ; import en repli. -->
        <UCard
          v-show="!(webcamActive && prefersFullscreenCamera)"
          class="ring-default/60 shadow-sm ring-1"
          :ui="{ body: 'p-3 sm:p-4 space-y-3' }"
        >
          <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <USwitch
              v-if="liveCameraSupported && webcamActive && !prefersFullscreenCamera"
              v-model="autoScan"
              label="Scan auto (caisse)"
              :description="
                autoScan ? 'Capture quand vous passez une carte puis la tenez immobile' : 'Capture manuelle uniquement'
              "
            />
            <div v-else />

            <div class="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:justify-end">
              <template v-if="liveCameraSupported">
                <UButton
                  v-if="!webcamActive"
                  size="xl"
                  color="primary"
                  variant="solid"
                  icon="i-lucide-video"
                  class="w-full justify-center text-base sm:w-auto"
                  :loading="webcamStarting"
                  :disabled="uploading"
                  @click.prevent="startWebcam"
                >
                  Activer la caméra (scan auto)
                </UButton>
                <template v-else>
                  <UButton
                    size="md"
                    color="primary"
                    variant="solid"
                    icon="i-lucide-camera"
                    :loading="uploading"
                    :disabled="!webcamReady"
                    @click.prevent="captureFromWebcam"
                  >
                    Capturer
                  </UButton>
                  <UButton
                    size="md"
                    color="neutral"
                    variant="soft"
                    icon="i-lucide-square"
                    :disabled="uploading"
                    @click.prevent="stopWebcam"
                  >
                    Arrêter
                  </UButton>
                </template>
                <UButton
                  size="md"
                  color="neutral"
                  variant="ghost"
                  icon="i-lucide-image-up"
                  :disabled="uploading"
                  @click.prevent="openNativeCamera"
                >
                  Importer
                </UButton>
              </template>

              <!-- Caméra live indisponible (HTTP / iOS) : on propose quand même
                   le scan auto (explique comment l'activer) + le déclenchement
                   natif qui marche en HTTP. -->
              <template v-else>
                <UButton
                  size="xl"
                  color="primary"
                  variant="solid"
                  icon="i-lucide-scan-line"
                  class="w-full justify-center text-base sm:w-auto"
                  :loading="webcamStarting"
                  :disabled="uploading"
                  @click.prevent="onActivateAutoScan"
                >
                  Activer le scan auto
                </UButton>
                <UButton
                  size="md"
                  color="neutral"
                  variant="ghost"
                  icon="i-lucide-image-up"
                  :disabled="uploading"
                  @click.prevent="openNativeCamera"
                >
                  Importer
                </UButton>
              </template>
            </div>
          </div>

          <UAlert
            v-if="showAutoScanHelp && isDev"
            color="info"
            variant="subtle"
            icon="i-lucide-info"
            title="Scan auto disponible en production"
            :close="true"
            description="Le scan auto (caméra en direct) n'est pas disponible en développement : le navigateur réserve la caméra continue à un contexte sécurisé (HTTPS). Ce sera actif en production. En attendant, « Importer » ouvre l'appareil photo (capture manuelle)."
            @update:open="showAutoScanHelp = false"
          />

          <input
            ref="fileInput"
            type="file"
            accept="image/*"
            capture="environment"
            class="hidden"
            @change="onFileChosen"
          />

          <!-- Aperçu caméra inline (desktop). -->
          <div v-if="webcamActive && !prefersFullscreenCamera" class="space-y-2">
            <div v-if="videoDevices.length > 1" class="flex flex-col gap-2 sm:flex-row sm:items-end">
              <UFormField label="Webcam" class="w-full sm:max-w-md">
                <USelect
                  v-model="selectedCameraId"
                  :items="videoDevices"
                  value-key="id"
                  label-key="label"
                  class="w-full"
                  @update:model-value="onCameraChanged"
                />
              </UFormField>
              <p v-if="webcamResolutionLabel" class="text-muted pb-0.5 text-xs sm:pb-2">
                Résolution&nbsp;: <span class="text-highlighted font-medium">{{ webcamResolutionLabel }}</span>
              </p>
            </div>
            <p v-else-if="webcamResolutionLabel" class="text-muted text-xs">
              Résolution&nbsp;: <span class="text-highlighted font-medium">{{ webcamResolutionLabel }}</span>
            </p>

            <div
              class="border-default bg-elevated/40 relative aspect-video w-full overflow-hidden rounded-xl border"
              @wheel.prevent="onWebcamWheel"
            >
              <video
                ref="videoEl"
                autoplay
                playsinline
                muted
                class="block h-full w-full bg-black object-cover transition-transform duration-150 ease-out"
                :style="webcamPreviewStyle"
              />
              <div v-if="!webcamReady" class="text-muted absolute inset-0 flex items-center justify-center text-xs">
                <UIcon name="i-lucide-loader-circle" class="text-primary mr-2 size-4 animate-spin" />
                Initialisation de la webcam…
              </div>

              <div
                v-if="webcamReady"
                class="bg-elevated/90 border-default/60 absolute top-2 right-2 left-2 flex items-center gap-2 rounded-lg border px-2 py-1.5 shadow-sm backdrop-blur-sm sm:left-auto sm:max-w-xs"
              >
                <UButton
                  size="xs"
                  color="neutral"
                  variant="ghost"
                  icon="i-lucide-minus"
                  :disabled="zoomLevel <= ZOOM_MIN"
                  aria-label="Dézoomer"
                  @click.prevent="adjustZoom(-0.25)"
                />
                <USlider
                  :model-value="zoomLevel"
                  :min="ZOOM_MIN"
                  :max="ZOOM_MAX"
                  :step="0.05"
                  class="min-w-0 flex-1"
                  @update:model-value="onZoomSliderChange"
                />
                <UButton
                  size="xs"
                  color="neutral"
                  variant="ghost"
                  icon="i-lucide-plus"
                  :disabled="zoomLevel >= ZOOM_MAX"
                  aria-label="Zoomer"
                  @click.prevent="adjustZoom(0.25)"
                />
                <span class="text-muted w-10 shrink-0 text-right text-xs tabular-nums">{{ zoomPercentLabel }}</span>
              </div>

              <div
                v-if="webcamReady && autoScan"
                class="bg-elevated/90 border-default/60 absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium shadow-sm backdrop-blur-sm"
              >
                <span
                  class="size-2 shrink-0 rounded-full"
                  :class="{
                    'bg-primary animate-pulse': autoScanStatus.color === 'primary',
                    'bg-success': autoScanStatus.color === 'success',
                    'bg-muted': autoScanStatus.color === 'neutral',
                  }"
                />
                <span class="text-highlighted">{{ autoScanStatus.label }}</span>
              </div>

              <button
                v-else
                type="button"
                :disabled="!webcamReady || uploading"
                class="bg-primary text-inverted absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full p-3 shadow-lg ring-2 ring-white/80 transition active:scale-95 disabled:opacity-50"
                aria-label="Capturer la carte"
                @click.prevent="captureFromWebcam"
              >
                <UIcon
                  :name="uploading ? 'i-lucide-loader-circle' : 'i-lucide-camera'"
                  class="size-6"
                  :class="uploading ? 'animate-spin' : ''"
                />
              </button>
            </div>
            <p class="text-muted text-[11px]">
              <template v-if="autoScan">
                Présentez chaque carte bien à plat dans le cadre et tenez-la immobile&nbsp;: elle est capturée toute
                seule, puis retirez-la pour enchaîner. Molette pour zoomer.
              </template>
              <template v-else>Molette sur l’aperçu pour zoomer. {{ zoomHint }}</template>
            </p>
          </div>

          <Teleport to="body">
            <div v-if="webcamActive && prefersFullscreenCamera" class="fixed inset-0 z-[300] flex flex-col bg-black">
              <div
                class="absolute top-0 right-0 left-0 z-10 flex items-center justify-between gap-2 p-3 pt-[max(0.75rem,env(safe-area-inset-top))]"
              >
                <UButton
                  size="sm"
                  color="neutral"
                  variant="soft"
                  icon="i-lucide-x"
                  class="bg-black/40 text-white backdrop-blur-sm"
                  @click.prevent="stopWebcam"
                >
                  Fermer
                </UButton>
                <UBadge
                  :color="connectionColor"
                  variant="solid"
                  size="sm"
                  class="bg-black/40 text-white backdrop-blur-sm"
                >
                  {{ connectionLabel }}
                </UBadge>
              </div>

              <div class="relative min-h-0 flex-1" @wheel.prevent="onWebcamWheel">
                <video
                  ref="videoEl"
                  autoplay
                  playsinline
                  muted
                  class="absolute inset-0 h-full w-full object-cover transition-transform duration-150 ease-out"
                  :style="webcamPreviewStyle"
                />
                <div
                  v-if="!webcamReady"
                  class="absolute inset-0 z-10 flex items-center justify-center bg-black/60 text-sm text-white/90"
                >
                  <UIcon name="i-lucide-loader-circle" class="text-primary mr-2 size-5 animate-spin" />
                  Ouverture de la caméra…
                </div>

                <div
                  v-if="webcamReady && autoScan"
                  class="absolute bottom-[max(5.5rem,env(safe-area-inset-bottom))] left-1/2 z-10 flex -translate-x-1/2 items-center gap-2 rounded-full border border-white/20 bg-black/55 px-4 py-2 text-sm font-medium text-white shadow-lg backdrop-blur-md"
                >
                  <span
                    class="size-2.5 shrink-0 rounded-full"
                    :class="{
                      'bg-primary animate-pulse': autoScanStatus.color === 'primary',
                      'bg-emerald-400': autoScanStatus.color === 'success',
                      'bg-white/50': autoScanStatus.color === 'neutral',
                    }"
                  />
                  {{ autoScanStatus.label }}
                </div>
              </div>

              <div
                class="border-t border-white/10 bg-black/80 px-3 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] backdrop-blur-md"
              >
                <div v-if="webcamReady" class="mb-2 flex items-center gap-2">
                  <UButton
                    size="xs"
                    color="neutral"
                    variant="ghost"
                    icon="i-lucide-minus"
                    class="text-white"
                    :disabled="zoomLevel <= ZOOM_MIN"
                    @click.prevent="adjustZoom(-0.25)"
                  />
                  <USlider
                    :model-value="zoomLevel"
                    :min="ZOOM_MIN"
                    :max="ZOOM_MAX"
                    :step="0.05"
                    class="min-w-0 flex-1"
                    @update:model-value="onZoomSliderChange"
                  />
                  <UButton
                    size="xs"
                    color="neutral"
                    variant="ghost"
                    icon="i-lucide-plus"
                    class="text-white"
                    :disabled="zoomLevel >= ZOOM_MAX"
                    @click.prevent="adjustZoom(0.25)"
                  />
                  <span class="w-10 text-right text-xs text-white/80 tabular-nums">{{ zoomPercentLabel }}</span>
                </div>
                <div class="flex items-center justify-between gap-2">
                  <USwitch v-model="autoScan" label="Scan auto" />
                  <UButton
                    v-if="!autoScan"
                    size="md"
                    color="primary"
                    icon="i-lucide-camera"
                    :loading="uploading"
                    :disabled="!webcamReady"
                    @click.prevent="captureFromWebcam"
                  >
                    Capturer
                  </UButton>
                </div>
              </div>
            </div>
          </Teleport>

          <UAlert
            v-if="webcamError"
            color="warning"
            variant="subtle"
            icon="i-lucide-camera-off"
            :description="webcamError"
          />

          <p class="text-muted text-xs">
            Astuce&nbsp;: la langue de la carte (français, japonais…) est reconnue automatiquement. Si la caméra n'est
            pas disponible, utilisez <span class="font-medium">Importer une photo</span> en repli.
          </p>
        </UCard>

        <ClientOnly>
          <div class="flex items-center gap-2 px-1">
            <span class="text-muted text-xs">Flux temps réel&nbsp;:</span>
            <UBadge :color="connectionColor" variant="subtle" size="sm">
              {{ connectionLabel }}
            </UBadge>
          </div>
        </ClientOnly>

        <UAlert
          v-if="lastError"
          color="warning"
          variant="subtle"
          icon="i-lucide-alert-triangle"
          :description="lastError"
        />

        <!-- Compteurs -->
        <div class="grid grid-cols-2 gap-2 sm:grid-cols-4 sm:gap-3">
          <div class="border-default bg-elevated/30 rounded-xl border p-2.5 text-center sm:p-3">
            <p class="text-muted text-[10px] uppercase">Scannées</p>
            <p class="text-highlighted text-lg font-semibold tabular-nums sm:text-xl">{{ counters.total }}</p>
          </div>
          <div class="border-default bg-elevated/30 rounded-xl border p-2.5 text-center sm:p-3">
            <p class="text-muted text-[10px] uppercase">Ajoutées</p>
            <p class="text-highlighted text-lg font-semibold tabular-nums sm:text-xl">{{ counters.added }}</p>
          </div>
          <div class="border-default bg-elevated/30 rounded-xl border p-2.5 text-center sm:p-3">
            <p class="text-muted text-[10px] uppercase">À vérifier</p>
            <p class="text-highlighted text-lg font-semibold tabular-nums sm:text-xl">{{ counters.needs_review }}</p>
          </div>
          <div class="border-default bg-elevated/30 rounded-xl border p-2.5 text-center sm:p-3">
            <p class="text-muted text-[10px] uppercase">En cours</p>
            <p class="text-highlighted text-lg font-semibold tabular-nums sm:text-xl">{{ counters.in_flight }}</p>
          </div>
        </div>

        <!-- Liste live -->
        <div v-if="events.length && counters.needs_review > 0" class="flex justify-end">
          <UButton
            size="sm"
            color="neutral"
            variant="soft"
            icon="i-lucide-eraser"
            :loading="clearingProblems"
            @click="onClearProblemScans"
          >
            Effacer échecs / à vérifier
          </UButton>
        </div>

        <div
          v-if="!events.length"
          class="border-default bg-elevated/20 rounded-xl border border-dashed p-6 text-center sm:p-8"
        >
          <UIcon name="i-lucide-scan-line" class="text-primary mx-auto size-9 sm:size-10" />
          <p class="text-highlighted mt-3 text-sm font-medium">Aucune carte scannée pour le moment</p>
          <p class="text-muted mt-1 text-xs">Le premier cliché apparaîtra ici dès qu'il sera identifié.</p>
        </div>

        <ul v-else class="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
          <li
            v-for="ev in events"
            :key="ev.event_id"
            class="border-default bg-elevated/30 flex items-center gap-3 rounded-xl border p-2 transition-colors sm:p-3"
            :class="rowAccentClass(ev.status)"
          >
            <div class="bg-muted/30 ring-default/40 h-16 w-12 shrink-0 overflow-hidden rounded-md ring sm:h-20 sm:w-14">
              <img
                v-if="thumbUrl(ev)"
                :src="thumbUrl(ev) ?? undefined"
                :alt="cardTitle(ev)"
                class="h-full w-full object-cover"
                referrerpolicy="no-referrer"
                decoding="async"
                loading="lazy"
              />
              <div v-else class="flex h-full items-center justify-center">
                <UIcon name="i-lucide-image" class="text-muted size-5" />
              </div>
            </div>

            <div class="min-w-0 flex-1 space-y-1">
              <div class="flex items-center gap-2">
                <p class="text-highlighted truncate text-sm font-medium">{{ cardTitle(ev) }}</p>
                <UBadge :color="statusBadgeColor(ev.status)" variant="subtle" size="sm">
                  {{ statusLabel(ev.status) }}
                </UBadge>
              </div>
              <p class="text-muted truncate text-xs">{{ subtitle(ev) }}</p>
              <p v-if="ev.error" class="text-warning text-xs">{{ ev.error }}</p>
            </div>

            <div class="flex shrink-0 flex-col items-end gap-1">
              <UButton
                v-if="ev.status === 'added' && ev.collection_card"
                size="xs"
                color="neutral"
                variant="ghost"
                icon="i-lucide-external-link"
                :to="`/collection/${ev.collection_card.id}`"
              >
                Ouvrir
              </UButton>
              <UButton
                v-else-if="ev.status === 'needs_review'"
                size="xs"
                color="primary"
                variant="soft"
                icon="i-lucide-plus"
                to="/collection/add"
              >
                Ajouter
              </UButton>
              <UIcon
                v-else-if="ev.status === 'queued' || ev.status === 'ocr_running' || ev.status === 'ocr_done'"
                name="i-lucide-loader-circle"
                class="text-primary size-4 animate-spin"
              />
              <UButton
                v-if="canDismissScan(ev.status)"
                size="xs"
                color="neutral"
                variant="ghost"
                icon="i-lucide-trash-2"
                :loading="dismissingId === ev.event_id"
                aria-label="Retirer de la liste"
                @click="onDismissScan(ev.event_id)"
              />
            </div>
          </li>
        </ul>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { ScanEvent, ScanEventStatus } from '~/composables/useScanStream'

definePageMeta({ middleware: 'auth', layout: 'default' })

useGoupixPageSeo(
  'Scanner mes cartes',
  'Scannez vos cartes Pokémon depuis votre téléphone et voyez-les apparaître dans votre collection en direct.',
)

// Le scan est conçu pour le téléphone (caméra arrière). Sur la version desktop
// (Tauri), on renvoie l'utilisateur vers sa collection pour éviter de proposer
// une fonctionnalité non pertinente — la sidebar masque déjà le raccourci.
const { isDesktopApp } = useDesktopRuntime()
if (import.meta.client && isDesktopApp.value) {
  void navigateTo('/collection', { replace: true })
}

const {
  events,
  connected,
  connecting,
  connectionMode,
  lastError,
  connect,
  disconnect,
  refreshRecent,
  uploadPhoto,
  dismissEvent,
  clearProblemEvents,
} = useScanStream()

const clearingProblems = ref(false)
const dismissingId = ref<string | null>(null)

// Physical language (fr / en / ja) is detected server-side from the OCR — no
// manual picker, so Japanese and French cards can be chained without a stop.
const SCAN_LANGUAGE = 'auto'

// "Cash register" mode: auto-capture a card the instant it is held steady.
const autoScan = ref(true)

const fileInput = ref<HTMLInputElement | null>(null)
const videoEl = ref<HTMLVideoElement | null>(null)
const uploading = ref(false)
const toast = useToast()

const ZOOM_MIN = 1
const ZOOM_MAX = 4
const WEBCAM_UPLOAD_COMPRESS = { maxEdge: 2560, quality: 0.9 } as const

/**
 * Live auto-capture ("caisse") is an optional bonus: `getUserMedia` only works
 * in a secure context (HTTPS / localhost). When it's unavailable (e.g. a phone
 * on plain `http://<lan-ip>`) we silently fall back to the native camera button
 * — `<input capture>` opens the OS camera over plain HTTP exactly as before.
 * No warning, no HTTPS requirement.
 */
const liveCameraSupported = computed<boolean>(() => {
  if (!import.meta.client) {
    return false
  }
  return (
    window.isSecureContext && 'mediaDevices' in navigator && typeof navigator.mediaDevices?.getUserMedia === 'function'
  )
})

/** Phones / tablets: fullscreen camera overlay (native-like). */
const prefersFullscreenCamera = computed<boolean>(() => {
  if (!import.meta.client) {
    return false
  }
  return window.matchMedia('(pointer: coarse)').matches
})

interface VideoDeviceOption {
  id: string
  label: string
}

interface HardwareZoomCaps {
  min: number
  max: number
  step: number
}

const webcamActive = ref(false)
const webcamStarting = ref(false)
const webcamReady = ref(false)
const webcamError = ref<string | null>(null)
const webcamResolutionLabel = ref<string | null>(null)
const videoDevices = ref<VideoDeviceOption[]>([])
const selectedCameraId = ref<string | undefined>(undefined)
const zoomLevel = ref(1)
/** Software zoom applied on top of hardware when the slider exceeds the optical range. */
const softwareZoomFactor = ref(1)

let webcamStream: MediaStream | null = null
let videoTrack: MediaStreamTrack | null = null
let hardwareZoomCaps: HardwareZoomCaps | null = null

const zoomPercentLabel = computed(() => `${Math.round(zoomLevel.value * 100)}%`)

const zoomHint = computed(() => {
  if (hardwareZoomCaps && hardwareZoomCaps.max > hardwareZoomCaps.min) {
    return 'Zoom optique de la webcam utilisé quand disponible.'
  }
  return 'Zoom numérique appliqué à la capture.'
})

const webcamPreviewStyle = computed(() => ({
  transform: `scale(${softwareZoomFactor.value})`,
  transformOrigin: 'center center',
}))

function clampZoom(value: number): number {
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Number(value.toFixed(2))))
}

/** Labels that usually mean front / selfie camera — never pick these for card scan. */
const FRONT_CAMERA_LABEL = /\b(front|user|selfie|self|facetime|face|frontal|avant|truedepth|inward)\b/i
/** Labels that usually mean rear / environment camera. */
const REAR_CAMERA_LABEL =
  /\b(back|rear|arrière|arriere|environment|wide|world|telephoto|très\s*grand\s*angle|ultra\s*wide)\b/i

function isFrontCameraLabel(label: string): boolean {
  return FRONT_CAMERA_LABEL.test(label)
}

function isRearCameraLabel(label: string): boolean {
  return REAR_CAMERA_LABEL.test(label)
}

function isFrontFacingTrack(track: MediaStreamTrack | undefined): boolean {
  if (!track) {
    return false
  }
  const settings = track.getSettings()
  if (settings.facingMode === 'user') {
    return true
  }
  if (settings.facingMode === 'environment') {
    return false
  }
  return isFrontCameraLabel(track.label)
}

/**
 * Pick the rear camera id from enumerated devices (labels are reliable after
 * the first `getUserMedia` permission grant).
 */
function pickRearCameraId(devices: VideoDeviceOption[]): string | undefined {
  const rear = devices.filter((d) => isRearCameraLabel(d.label) && !isFrontCameraLabel(d.label))
  if (rear.length) {
    return rear[0]?.id
  }
  const notFront = devices.filter((d) => !isFrontCameraLabel(d.label))
  if (notFront.length) {
    // On some phones the rear cam is listed last when labels are generic ("Caméra 2").
    return notFront[notFront.length - 1]?.id
  }
  return undefined
}

function buildVideoConstraints(): MediaTrackConstraints {
  const hd: MediaTrackConstraints = {
    width: { min: 1280, ideal: 3840 },
    height: { min: 720, ideal: 2160 },
    frameRate: { ideal: 30 },
  }
  if (selectedCameraId.value) {
    return { ...hd, deviceId: { exact: selectedCameraId.value } }
  }
  // `exact` — never fall back to selfie when scanning cards.
  return { ...hd, facingMode: { exact: 'environment' } }
}

async function enumerateVideoDevices(): Promise<void> {
  try {
    const devices = await navigator.mediaDevices.enumerateDevices()
    const all = devices
      .filter((d) => d.kind === 'videoinput')
      .map((d, i) => ({
        id: d.deviceId,
        label: d.label || `Caméra ${i + 1}`,
      }))
    // UI list: rear cameras only (scan never uses selfie).
    videoDevices.value = all.filter((d) => !isFrontCameraLabel(d.label))
    const rearId = pickRearCameraId(all)
    if (rearId) {
      selectedCameraId.value = rearId
    }
  } catch {
    videoDevices.value = []
  }
}

function updateResolutionLabel(track: MediaStreamTrack): void {
  const s = track.getSettings()
  const w = s.width
  const h = s.height
  webcamResolutionLabel.value = w && h ? `${w}×${h}` : null
}

function readHardwareZoomCaps(track: MediaStreamTrack): void {
  const caps = track.getCapabilities?.()
  if (caps?.zoom && typeof caps.zoom.min === 'number' && typeof caps.zoom.max === 'number') {
    hardwareZoomCaps = {
      min: caps.zoom.min,
      max: caps.zoom.max,
      step: caps.zoom.step ?? 0.1,
    }
  } else {
    hardwareZoomCaps = null
  }
}

async function openVideoStream(): Promise<MediaStream> {
  const attempts: MediaTrackConstraints[] = []

  if (selectedCameraId.value) {
    attempts.push({
      deviceId: { exact: selectedCameraId.value },
      width: { ideal: 1920 },
      height: { ideal: 1080 },
      frameRate: { ideal: 30 },
    })
  }

  attempts.push(
    buildVideoConstraints(),
    {
      facingMode: { exact: 'environment' },
      width: { ideal: 1920 },
      height: { ideal: 1080 },
    },
    { facingMode: { exact: 'environment' } },
    {
      facingMode: { ideal: 'environment' },
      width: { ideal: 1280 },
      height: { ideal: 720 },
    },
  )

  const rejectFrontTrack = (stream: MediaStream): MediaStream | null => {
    const track = stream.getVideoTracks()[0]
    if (track && isFrontFacingTrack(track)) {
      stream.getTracks().forEach((t) => t.stop())
      return null
    }
    return stream
  }

  let lastErr: unknown
  for (const video of attempts) {
    try {
      const stream = rejectFrontTrack(await navigator.mediaDevices.getUserMedia({ video, audio: false }))
      if (stream) {
        return stream
      }
    } catch (e) {
      lastErr = e
    }
  }

  // Desktop web: built-in webcam has no `environment` facing — allow default camera.
  if (!prefersFullscreenCamera.value) {
    try {
      const stream = rejectFrontTrack(
        await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 1920 }, height: { ideal: 1080 }, frameRate: { ideal: 30 } },
          audio: false,
        }),
      )
      if (stream) {
        return stream
      }
    } catch (e) {
      lastErr = e
    }
  }

  throw lastErr instanceof Error ? lastErr : new Error('Impossible d’ouvrir la caméra arrière')
}

async function applyZoomToTrack(level: number): Promise<void> {
  const clamped = clampZoom(level)
  zoomLevel.value = clamped

  let hardwareMagnification = 1
  if (hardwareZoomCaps && videoTrack && hardwareZoomCaps.max > hardwareZoomCaps.min) {
    const t = (clamped - ZOOM_MIN) / (ZOOM_MAX - ZOOM_MIN)
    const target = hardwareZoomCaps.min + t * (hardwareZoomCaps.max - hardwareZoomCaps.min)
    try {
      await videoTrack.applyConstraints({ zoom: target } as MediaTrackConstraintSet)
      hardwareMagnification = target / hardwareZoomCaps.min
    } catch {
      hardwareMagnification = 1
    }
  }

  softwareZoomFactor.value = Math.max(1, clamped / hardwareMagnification)
}

function adjustZoom(delta: number): void {
  void applyZoomToTrack(zoomLevel.value + delta)
}

function onZoomSliderChange(value: number | number[] | undefined): void {
  const raw = Array.isArray(value) ? value[0] : value
  if (raw === undefined) {
    return
  }
  void applyZoomToTrack(raw)
}

function onWebcamWheel(e: WheelEvent): void {
  if (!webcamReady.value) {
    return
  }
  const delta = e.deltaY < 0 ? 0.1 : -0.1
  void applyZoomToTrack(zoomLevel.value + delta)
}

async function attachStreamToPreview(stream: MediaStream): Promise<void> {
  videoTrack = stream.getVideoTracks()[0] ?? null
  if (videoTrack) {
    readHardwareZoomCaps(videoTrack)
    updateResolutionLabel(videoTrack)
    try {
      await videoTrack.applyConstraints({
        width: { ideal: 3840 },
        height: { ideal: 2160 },
      })
      updateResolutionLabel(videoTrack)
    } catch {
      /* device may reject a second bump — keep negotiated resolution */
    }
  }

  webcamStream = stream
  webcamActive.value = true
  zoomLevel.value = 1
  softwareZoomFactor.value = 1
  await nextTick()

  if (!videoEl.value) {
    return
  }
  videoEl.value.srcObject = stream
  const onVideoReady = (): void => {
    webcamReady.value = true
    if (videoTrack) {
      updateResolutionLabel(videoTrack)
    }
    void applyZoomToTrack(zoomLevel.value)
  }
  videoEl.value.onloadedmetadata = onVideoReady
  videoEl.value.onloadeddata = onVideoReady
  if (videoEl.value.readyState >= 2) {
    onVideoReady()
  }
  try {
    await videoEl.value.play()
  } catch {
    /* autoplay can fail when the user hasn't gestured; ignored. */
  }
}

async function startWebcam(preserveDeviceSelection = false): Promise<void> {
  if (webcamActive.value || webcamStarting.value) {
    return
  }
  webcamError.value = null
  webcamStarting.value = true
  webcamReady.value = false
  if (!preserveDeviceSelection) {
    selectedCameraId.value = undefined
  }
  try {
    let stream = await openVideoStream()

    if (!preserveDeviceSelection) {
      await enumerateVideoDevices()

      let track = stream.getVideoTracks()[0]
      const activeId = track?.getSettings().deviceId
      const rearId = selectedCameraId.value

      const mustSwitchToRear =
        Boolean(rearId && activeId && activeId !== rearId) || Boolean(track && isFrontFacingTrack(track))

      if (mustSwitchToRear) {
        stream.getTracks().forEach((t) => t.stop())
        if (!rearId) {
          throw new Error('Caméra arrière introuvable sur cet appareil.')
        }
        selectedCameraId.value = rearId
        stream = await openVideoStream()
        track = stream.getVideoTracks()[0]
        if (track && isFrontFacingTrack(track)) {
          throw new Error('La caméra avant s’est ouverte à la place de la caméra arrière.')
        }
      }
    } else {
      const track = stream.getVideoTracks()[0]
      if (track && isFrontFacingTrack(track)) {
        stream.getTracks().forEach((t) => t.stop())
        throw new Error('La caméra avant s’est ouverte à la place de la caméra arrière.')
      }
    }

    await attachStreamToPreview(stream)
  } catch (err) {
    webcamError.value =
      err instanceof Error
        ? `Accès caméra refusé : ${err.message}`
        : 'Accès caméra refusé. Autorisez la caméra arrière dans le navigateur pour utiliser le scan en direct.'
    stopWebcam()
  } finally {
    webcamStarting.value = false
  }
}

async function onCameraChanged(deviceId: string | undefined): Promise<void> {
  if (!webcamActive.value || !deviceId) {
    return
  }
  const picked = videoDevices.value.find((d) => d.id === deviceId)
  if (picked && isFrontCameraLabel(picked.label)) {
    toast.add({
      title: 'Caméra avant ignorée',
      description: 'Utilisez la caméra arrière pour scanner vos cartes.',
      color: 'warning',
    })
    selectedCameraId.value = pickRearCameraId(videoDevices.value)
    stopWebcam()
    await startWebcam(true)
    return
  }
  stopWebcam()
  await startWebcam(true)
}

function stopWebcam(): void {
  if (webcamStream) {
    webcamStream.getTracks().forEach((t) => t.stop())
    webcamStream = null
  }
  videoTrack = null
  hardwareZoomCaps = null
  if (videoEl.value) {
    videoEl.value.srcObject = null
  }
  webcamActive.value = false
  webcamReady.value = false
  webcamResolutionLabel.value = null
  zoomLevel.value = 1
  softwareZoomFactor.value = 1
}

async function captureFromWebcam(): Promise<void> {
  if (uploading.value || !webcamReady.value || !videoEl.value) {
    return
  }
  const video = videoEl.value
  const fullW = video.videoWidth
  const fullH = video.videoHeight
  if (!fullW || !fullH) {
    return
  }

  const z = softwareZoomFactor.value
  const cropW = fullW / z
  const cropH = fullH / z
  const sx = (fullW - cropW) / 2
  const sy = (fullH - cropH) / 2

  const canvas = document.createElement('canvas')
  canvas.width = Math.round(cropW)
  canvas.height = Math.round(cropH)
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    return
  }
  ctx.drawImage(video, sx, sy, cropW, cropH, 0, 0, canvas.width, canvas.height)

  const blob = await new Promise<Blob | null>((resolve) => {
    canvas.toBlob((b) => resolve(b), 'image/jpeg', 0.95)
  })
  if (!blob) {
    return
  }
  const file = new File([blob], `webcam-${Date.now()}.jpg`, { type: 'image/jpeg' })
  uploading.value = true
  try {
    await uploadPhoto(file, SCAN_LANGUAGE, undefined, WEBCAM_UPLOAD_COMPRESS)
  } catch (err) {
    toast.add({
      title: 'Envoi impossible',
      description: apiErrorMessage(err),
      color: 'error',
    })
  } finally {
    uploading.value = false
  }
}

const connectionColor = computed<'success' | 'warning' | 'neutral'>(() => {
  if (connected.value) {
    return 'success'
  }
  if (connecting.value) {
    return 'warning'
  }
  return 'neutral'
})

const connectionLabel = computed(() => {
  if (connected.value && connectionMode.value === 'websocket') {
    return 'Connecté'
  }
  if (connected.value && connectionMode.value === 'polling') {
    return 'Connecté'
  }
  if (connecting.value) {
    return 'Connexion…'
  }
  return 'Déconnecté'
})

const counters = computed(() => {
  let added = 0
  let needs_review = 0
  let in_flight = 0
  for (const ev of events.value) {
    if (ev.status === 'added') {
      added += 1
    } else if (ev.status === 'needs_review' || ev.status === 'failed') {
      needs_review += 1
    } else {
      in_flight += 1
    }
  }
  return { total: events.value.length, added, needs_review, in_flight }
})

function thumbUrl(ev: ScanEvent): string | null {
  return ev.collection_card?.image_url ?? ev.image_preview_data_url ?? null
}

function cardTitle(ev: ScanEvent): string {
  if (ev.collection_card?.display_name) {
    return ev.collection_card.display_name
  }
  const ocrName = ev.ocr?.pokemon_name_english as string | undefined
  if (ocrName) {
    return ocrName
  }
  const printed = ev.ocr?.pokemon_name as string | undefined
  if (printed) {
    return printed
  }
  return 'Carte en cours d’identification…'
}

function subtitle(ev: ScanEvent): string {
  const parts: string[] = []
  const setCode = (ev.ocr?.set_code as string | undefined) ?? ev.collection_card?.set_code
  const cardNum = (ev.ocr?.card_number as string | undefined) ?? ev.collection_card?.card_number
  if (setCode) {
    parts.push(String(setCode).toUpperCase())
  }
  if (cardNum) {
    parts.push(`#${cardNum}`)
  }
  if (!parts.length) {
    parts.push('—')
  }
  const lang = ev.physical_language?.toLowerCase()
  if (lang === 'fr' || lang === 'en' || lang === 'ja') {
    parts.push(lang.toUpperCase())
  }
  if (ev.status === 'added' && ev.created === false) {
    parts.push('quantité +1')
  }
  return parts.join(' · ')
}

function statusLabel(s: ScanEventStatus): string {
  switch (s) {
    case 'queued':
      return 'En file'
    case 'ocr_running':
      return 'OCR…'
    case 'ocr_done':
      return 'Identification…'
    case 'needs_review':
      return 'À vérifier'
    case 'added':
      return 'Ajoutée'
    case 'failed':
      return 'Échec'
  }
}

function statusBadgeColor(s: ScanEventStatus): 'primary' | 'success' | 'warning' | 'error' | 'neutral' {
  switch (s) {
    case 'added':
      return 'success'
    case 'needs_review':
      return 'warning'
    case 'failed':
      return 'error'
    case 'queued':
    case 'ocr_running':
    case 'ocr_done':
      return 'primary'
    default:
      return 'neutral'
  }
}

function canDismissScan(s: ScanEventStatus): boolean {
  return s === 'added' || s === 'failed' || s === 'needs_review'
}

async function onDismissScan(eventId: string): Promise<void> {
  dismissingId.value = eventId
  try {
    await dismissEvent(eventId)
  } catch (err) {
    toast.add({
      title: 'Suppression impossible',
      description: apiErrorMessage(err),
      color: 'error',
    })
  } finally {
    dismissingId.value = null
  }
}

async function onClearProblemScans(): Promise<void> {
  clearingProblems.value = true
  try {
    const removed = await clearProblemEvents()
    toast.add({
      title: removed ? `${removed} scan(s) retiré(s)` : 'Liste déjà vide',
      color: 'success',
    })
  } catch (err) {
    toast.add({
      title: 'Effacement impossible',
      description: apiErrorMessage(err),
      color: 'error',
    })
  } finally {
    clearingProblems.value = false
  }
}

function rowAccentClass(s: ScanEventStatus): string {
  if (s === 'added') {
    return 'ring-success/20 ring'
  }
  if (s === 'failed' || s === 'needs_review') {
    return 'ring-warning/20 ring'
  }
  return ''
}

function openNativeCamera(): void {
  if (!fileInput.value) {
    return
  }
  fileInput.value.value = ''
  fileInput.value.click()
}

// The flag workaround only makes sense in local dev (HTTP). In prod the site
// is HTTPS so the live camera just works — never surface this there.
const isDev = import.meta.dev
const showAutoScanHelp = ref(false)

/**
 * "Activer le scan auto": start the live camera when the browser allows it
 * (secure context = HTTPS / prod). In dev (HTTP) `getUserMedia` is blocked by
 * the browser, so we just surface a note that it's a production-only feature.
 * @returns {void} Nothing.
 */
function onActivateAutoScan(): void {
  if (liveCameraSupported.value) {
    void startWebcam()
    return
  }
  showAutoScanHelp.value = isDev
}

async function onFileChosen(e: Event): Promise<void> {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) {
    return
  }
  uploading.value = true
  try {
    await uploadPhoto(file, SCAN_LANGUAGE)
  } catch (err) {
    toast.add({
      title: 'Envoi impossible',
      description: apiErrorMessage(err),
      color: 'error',
    })
  } finally {
    uploading.value = false
    input.value = ''
  }
}

// Cash-register auto-capture: shoot a card as soon as it is held steady, then
// re-arm only after it leaves the frame (so one card is never scanned twice).
const autoScanEnabled = computed(() => webcamActive.value && webcamReady.value && autoScan.value)
const { phase: autoScanPhase } = useCardAutoScan({
  video: videoEl,
  enabled: autoScanEnabled,
  busy: uploading,
  onCapture: captureFromWebcam,
})

const autoScanStatus = computed<{ label: string; color: 'primary' | 'success' | 'neutral' }>(() => {
  if (uploading.value) {
    return { label: 'Envoi…', color: 'primary' }
  }
  switch (autoScanPhase.value) {
    case 'watching':
      return { label: 'Placez ou passez une carte', color: 'neutral' }
    case 'settling':
      return { label: 'Lecture… tenez la carte immobile', color: 'primary' }
    case 'captured':
      return { label: 'Carte capturée', color: 'success' }
    case 'cooldown':
      return { label: 'Retirez la carte pour la suivante', color: 'success' }
    default:
      return { label: 'Caméra en pause', color: 'neutral' }
  }
})

onMounted(async () => {
  await refreshRecent()
  await connect()
  if (liveCameraSupported.value) {
    await startWebcam()
  }
})

onBeforeUnmount(() => {
  stopWebcam()
  disconnect()
})
</script>
