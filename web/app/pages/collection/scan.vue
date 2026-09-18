<template>
  <UDashboardPanel id="collection-scan">
    <template #header>
      <UDashboardNavbar>
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #title>
          <span class="app-label flex items-center gap-1.5 !text-[0.65rem]">
            <UIcon name="i-lucide-flame" class="h-3 w-3 text-(--app-accent)" />
            Collection
          </span>
        </template>
        <template #right>
          <UButton to="/collection" color="neutral" variant="ghost" icon="i-lucide-album"> Ma collection </UButton>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="w-full space-y-4 px-3 py-4 sm:space-y-5 sm:px-5 sm:py-5">
        <GoupixDexPageHeader
          title="Scanner mes cartes"
          description="Photographiez vos cartes à la chaîne : langue reconnue automatiquement, capture en mode caisse (HTTPS) et arrivée en temps réel dans la collection."
        />

        <!-- Desktop (Tauri) : pas de caméra pertinente — QR code vers le téléphone,
             la page sert d'écran de contrôle du flux temps réel. -->
        <UCard v-if="isDesktopApp" :ui="{ body: 'p-4 sm:p-5' }">
          <div class="flex flex-col items-center gap-5 sm:flex-row sm:items-center">
            <img
              v-if="phoneScanQrDataUrl"
              :src="phoneScanQrDataUrl"
              alt="QR code vers la page de scan"
              class="h-36 w-36 shrink-0 rounded-xl bg-white p-2"
            />
            <div class="min-w-0 space-y-1.5 text-center sm:text-left">
              <p class="text-highlighted text-sm font-semibold">Scannez avec votre téléphone</p>
              <p class="text-muted text-sm leading-relaxed">
                Ouvrez ce QR code avec l'appareil photo du téléphone : la page de scan s'ouvre avec la caméra arrière.
                Les cartes scannées apparaissent ici en temps réel.
              </p>
              <p class="text-muted font-mono text-xs break-all">{{ phoneScanUrl }}</p>
            </div>
          </div>
        </UCard>

        <!-- Caméra live + auto-capture (téléphone et web) ; import en repli. -->
        <UCard
          v-else
          v-show="!(webcamActive && prefersFullscreenCamera)"
          class="ring-default ring-1"
          :ui="{ body: 'p-3 sm:p-4 space-y-3' }"
        >
          <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <USwitch
              v-if="liveCameraSupported && webcamActive && !prefersFullscreenCamera"
              v-model="autoScan"
              label="Scan auto (caisse)"
              :description="
                autoScan
                  ? 'Capture dès qu\'une carte est tracée — vous pouvez bouger ou pivoter'
                  : 'Capture manuelle uniquement'
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

          <div class="flex flex-wrap items-center gap-2">
            <div class="border-default flex overflow-hidden rounded-full border">
              <button
                type="button"
                class="flex cursor-pointer items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold transition-colors"
                :class="scanDirection === 'in' ? 'bg-success text-inverted' : 'text-muted hover:text-highlighted'"
                @click="setScanDirection('in')"
              >
                <UIcon name="i-lucide-plus" class="size-3.5" />
                Entrée
              </button>
              <button
                type="button"
                class="flex cursor-pointer items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold transition-colors"
                :class="scanDirection === 'out' ? 'bg-error text-inverted' : 'text-muted hover:text-highlighted'"
                @click="setScanDirection('out')"
              >
                <UIcon name="i-lucide-minus" class="size-3.5" />
                Sortie
              </button>
            </div>
            <p class="text-muted text-xs">
              {{
                scanDirection === 'in'
                  ? 'Chaque carte scannée est ajoutée à la collection.'
                  : 'Chaque carte scannée est retirée de la collection (vendue / échangée).'
              }}
            </p>
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
                ref="videoElInline"
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
                Présentez chaque carte dans le cadre&nbsp;: dès qu'elle est tracée, elle est capturée toute seule, puis
                retirez-la pour enchaîner. Molette pour zoomer.
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
                <div class="flex items-center gap-2">
                  <UButton
                    size="sm"
                    color="neutral"
                    variant="solid"
                    :icon="soundOn ? 'i-lucide-volume-2' : 'i-lucide-volume-x'"
                    class="bg-black/40 text-white backdrop-blur-sm"
                    :aria-label="soundOn ? 'Couper le son' : 'Activer le son'"
                    @click.prevent="soundOn = !soundOn"
                  />
                  <UButton
                    v-if="torchSupported"
                    size="sm"
                    :color="torchOn ? 'warning' : 'neutral'"
                    variant="solid"
                    :icon="torchOn ? 'i-lucide-zap' : 'i-lucide-zap-off'"
                    class="backdrop-blur-sm"
                    :class="torchOn ? '' : 'bg-black/40 text-white'"
                    :aria-label="torchOn ? 'Éteindre le flash' : 'Allumer le flash'"
                    @click.prevent="toggleTorch"
                  />
                  <UBadge
                    :color="connectionColor"
                    variant="solid"
                    size="sm"
                    class="bg-black/40 text-white backdrop-blur-sm"
                  >
                    {{ connectionLabel }}
                  </UBadge>
                </div>
              </div>

              <div class="relative min-h-0 flex-1" @wheel.prevent="onWebcamWheel">
                <video
                  ref="videoElFullscreen"
                  autoplay
                  playsinline
                  muted
                  class="absolute inset-0 h-full w-full object-cover transition-transform duration-150 ease-out"
                  :style="webcamPreviewStyle"
                />
                <svg
                  v-if="cardOverlay && videoIntrinsicW && videoIntrinsicH"
                  class="pointer-events-none absolute inset-0 h-full w-full transition-transform duration-150 ease-out"
                  :style="webcamPreviewStyle"
                  :viewBox="`0 0 ${videoIntrinsicW} ${videoIntrinsicH}`"
                  preserveAspectRatio="xMidYMid slice"
                >
                  <rect
                    :x="cardOverlay.cx - cardOverlay.w / 2"
                    :y="cardOverlay.cy - cardOverlay.h / 2"
                    :width="cardOverlay.w"
                    :height="cardOverlay.h"
                    :rx="Math.min(cardOverlay.w, cardOverlay.h) * 0.045"
                    :ry="Math.min(cardOverlay.w, cardOverlay.h) * 0.045"
                    :transform="`rotate(${cardOverlay.angleDeg} ${cardOverlay.cx} ${cardOverlay.cy})`"
                    fill="rgba(249,115,22,0.10)"
                    stroke="#f97316"
                    stroke-width="6"
                    stroke-linejoin="round"
                  />
                </svg>
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

                <Transition name="fade">
                  <div
                    v-if="latestAdded?.collection_card"
                    class="absolute right-3 bottom-3 left-3 z-20 flex items-center gap-3 rounded-2xl border border-white/15 bg-black/70 p-3 text-white shadow-2xl backdrop-blur-md"
                  >
                    <div class="h-20 w-14 shrink-0 overflow-hidden rounded-md bg-white/10">
                      <img
                        v-if="latestAdded.collection_card.image_url"
                        :src="latestAdded.collection_card.image_url"
                        :alt="latestAdded.collection_card.display_name"
                        class="h-full w-full object-cover"
                        referrerpolicy="no-referrer"
                        decoding="async"
                      />
                    </div>
                    <div class="min-w-0 flex-1">
                      <p class="truncate text-sm font-semibold">
                        {{ latestAdded.collection_card.display_name }}
                      </p>
                      <p class="truncate text-xs text-white/70">
                        {{ latestAdded.collection_card.set_name || latestAdded.collection_card.tcgdex_set_id }} · #{{
                          latestAdded.collection_card.card_number
                        }}
                      </p>
                      <p
                        class="mt-0.5 text-xs"
                        :class="latestAdded.status === 'removed' ? 'text-orange-300' : 'text-emerald-400'"
                      >
                        {{ outcomeLine(latestAdded) }}
                      </p>
                    </div>
                    <div class="flex shrink-0 flex-col gap-1">
                      <UButton
                        size="xs"
                        color="neutral"
                        variant="solid"
                        icon="i-lucide-external-link"
                        class="bg-white/15"
                        :to="`/collection/${latestAdded.collection_card.id}`"
                      >
                        Ouvrir
                      </UButton>
                      <UButton
                        size="xs"
                        color="neutral"
                        variant="ghost"
                        icon="i-lucide-x"
                        class="text-white"
                        aria-label="Masquer"
                        @click.prevent="dismissedAddedId = latestAdded?.event_id ?? null"
                      />
                    </div>
                  </div>
                </Transition>
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
                <div class="mb-2 flex justify-center">
                  <div class="flex overflow-hidden rounded-full border border-white/20 bg-black/40">
                    <button
                      type="button"
                      class="flex cursor-pointer items-center gap-1.5 px-5 py-2 text-sm font-semibold transition-colors"
                      :class="scanDirection === 'in' ? 'bg-emerald-500 text-white' : 'text-white/70'"
                      @click="setScanDirection('in')"
                    >
                      <UIcon name="i-lucide-plus" class="size-4" />
                      Entrée
                    </button>
                    <button
                      type="button"
                      class="flex cursor-pointer items-center gap-1.5 px-5 py-2 text-sm font-semibold transition-colors"
                      :class="scanDirection === 'out' ? 'bg-red-500 text-white' : 'text-white/70'"
                      @click="setScanDirection('out')"
                    >
                      <UIcon name="i-lucide-minus" class="size-4" />
                      Sortie
                    </button>
                  </div>
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

          <Teleport to="body">
            <Transition name="fade">
              <div v-if="flashKind" class="pointer-events-none fixed inset-0 z-[400]" :class="flashOverlayClass" />
            </Transition>
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
        <div class="grid grid-cols-3 gap-2 sm:grid-cols-5 sm:gap-3">
          <div class="border-default bg-elevated/30 rounded-xl border p-2.5 text-center sm:p-3">
            <p class="text-muted text-[10px] uppercase">Scannées</p>
            <p class="text-highlighted text-lg font-semibold tabular-nums sm:text-xl">{{ counters.total }}</p>
          </div>
          <div class="border-default bg-elevated/30 rounded-xl border p-2.5 text-center sm:p-3">
            <p class="text-muted text-[10px] uppercase">Ajoutées</p>
            <p class="text-highlighted text-lg font-semibold tabular-nums sm:text-xl">{{ counters.added }}</p>
          </div>
          <div class="border-default bg-elevated/30 rounded-xl border p-2.5 text-center sm:p-3">
            <p class="text-muted text-[10px] uppercase">Retirées</p>
            <p class="text-highlighted text-lg font-semibold tabular-nums sm:text-xl">{{ counters.removed }}</p>
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
        <div v-if="displayedEvents.length && counters.needs_review > 0" class="flex justify-end">
          <UButton
            size="sm"
            color="neutral"
            variant="soft"
            icon="i-lucide-eraser"
            :loading="clearingProblems"
            @click="onClearProblemScans"
          >
            Effacer les échecs
          </UButton>
        </div>

        <div
          v-if="!displayedEvents.length"
          class="border-default bg-elevated/20 rounded-xl border border-dashed p-6 text-center sm:p-8"
        >
          <UIcon name="i-lucide-scan-line" class="text-primary mx-auto size-9 sm:size-10" />
          <p class="text-highlighted mt-3 text-sm font-medium">Aucune carte scannée pour le moment</p>
          <p class="text-muted mt-1 text-xs">Le premier cliché apparaîtra ici dès qu'il sera identifié.</p>
        </div>

        <ul v-else class="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
          <li
            v-for="ev in displayedEvents"
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
                v-if="(ev.status === 'added' || (ev.status === 'removed' && !ev.deleted)) && ev.collection_card"
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
import { renderSVG } from 'uqr'
import type { ScanDirection, ScanEvent, ScanEventStatus } from '~/composables/useScanStream'

definePageMeta({ middleware: 'auth', layout: 'default' })

useGoupixPageSeo(
  'Scanner mes cartes',
  'Scannez vos cartes Pokémon depuis votre téléphone et voyez-les apparaître dans votre collection en direct.',
)

// Le scan photo se fait depuis le téléphone (caméra arrière). Sur la version
// desktop (Tauri), la page sert d'écran de contrôle : QR code pour ouvrir le
// scan sur le téléphone + flux temps réel des cartes qui rentrent / sortent.
const { isDesktopApp } = useDesktopRuntime()
const runtimeConfig = useRuntimeConfig()

/** URL of this page on the deployed site — what the phone should open. */
const phoneScanUrl = computed<string>(() => {
  let base = String(runtimeConfig.public.siteUrl || '').replace(/\/$/, '')
  // `NUXT_PUBLIC_SITE_URL=` (empty) overrides the default at runtime; fall
  // back to the current origin when it is a reachable http(s) URL.
  if (!base && import.meta.client && /^https?:/i.test(window.location.origin)) {
    base = window.location.origin
  }
  return `${base || 'https://goupixdex.dibodev.fr'}/collection/scan`
})

/** QR code of {@link phoneScanUrl} as an SVG data URL (desktop helper panel). */
const phoneScanQrDataUrl = computed<string>(() => {
  try {
    const svg = renderSVG(phoneScanUrl.value, { pixelSize: 4 })
    return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
  } catch {
    return ''
  }
})

const {
  events,
  connected,
  connecting,
  connectionMode,
  lastError,
  lastDroppedEvent,
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

/**
 * Cash-register direction: `in` adds each scanned card to the collection,
 * `out` removes it (sold / traded away). Resets to `in` on every visit —
 * a sticky "out" mode would silently empty the binder.
 */
const scanDirection = ref<ScanDirection>('in')

/**
 * Switch the cash-register direction (with an audio unlock, since it's a gesture).
 * @param direction - `in` or `out`.
 */
function setScanDirection(direction: ScanDirection): void {
  scanDirection.value = direction
  unlockAudio()
}

/** Tint of the outcome flash overlay. */
const flashOverlayClass = computed<string>(() => {
  if (flashKind.value === 'success') {
    return 'bg-emerald-500/35'
  }
  if (flashKind.value === 'removed') {
    return 'bg-orange-500/35'
  }
  return 'bg-red-600/40'
})

const fileInput = ref<HTMLInputElement | null>(null)
/**
 * The inline (desktop) and fullscreen (phone) previews are two distinct
 * `<video>` elements. They used to share one `ref`, and whichever unmounted
 * last nulled it — black camera with no error. One ref each + a computed
 * pointing at the active one.
 */
const videoElInline = ref<HTMLVideoElement | null>(null)
const videoElFullscreen = ref<HTMLVideoElement | null>(null)
const videoEl = computed<HTMLVideoElement | null>(() =>
  prefersFullscreenCamera.value ? videoElFullscreen.value : videoElInline.value,
)
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
/** Hardware torch / flash (rear camera only; not all devices expose it). */
const torchSupported = ref(false)
const torchOn = ref(false)
/** Intrinsic camera resolution — drives the tracking-overlay SVG viewBox. */
const videoIntrinsicW = ref(0)
const videoIntrinsicH = ref(0)
/** Success beep on each scan (toggle from the camera bar). */
const soundOn = ref(true)
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
  // 1920 is plenty: the OCR crop is 630×880. Asking for 4K used to make every
  // capture-frame grab allocate ~33 MB and freeze mid-range phones.
  const hd: MediaTrackConstraints = {
    width: { min: 1280, ideal: 1920 },
    height: { min: 720, ideal: 1080 },
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
      // Android Chrome expects `advanced` for zoom (like the torch); keep the
      // plain form as a fallback for engines that only accept the direct key.
      await videoTrack.applyConstraints({
        advanced: [{ zoom: target } as unknown as MediaTrackConstraintSet],
      })
      hardwareMagnification = target / hardwareZoomCaps.min
    } catch {
      try {
        await videoTrack.applyConstraints({ zoom: target } as MediaTrackConstraintSet)
        hardwareMagnification = target / hardwareZoomCaps.min
      } catch {
        hardwareMagnification = 1
      }
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

/** Detect torch capability on the active rear track (Chrome/Android, some iOS). */
function readTorchCap(track: MediaStreamTrack): void {
  try {
    const caps = track.getCapabilities?.() as (MediaTrackCapabilities & { torch?: boolean }) | undefined
    torchSupported.value = Boolean(caps && caps.torch)
  } catch {
    torchSupported.value = false
  }
  torchOn.value = false
}

/** Toggle the hardware flash; silently no-op if the device rejects it. */
async function toggleTorch(): Promise<void> {
  if (!videoTrack || !torchSupported.value) {
    return
  }
  const next = !torchOn.value
  try {
    await videoTrack.applyConstraints({
      advanced: [{ torch: next } as unknown as MediaTrackConstraintSet],
    })
    torchOn.value = next
  } catch {
    torchSupported.value = false
  }
}

async function attachStreamToPreview(stream: MediaStream): Promise<void> {
  videoTrack = stream.getVideoTracks()[0] ?? null
  if (videoTrack) {
    readHardwareZoomCaps(videoTrack)
    readTorchCap(videoTrack)
    updateResolutionLabel(videoTrack)
    // Camera stolen by a call / another app / revoked permission: recover
    // instead of leaving a frozen black preview with the detector running.
    videoTrack.onended = onCameraTrackEnded
  }

  webcamStream = stream
  webcamActive.value = true
  // Default to a moderate zoom so the card "fills" the frame on opening —
  // wide-angle phone cameras render the card very small at 1×. The user can
  // dezoom with the slider; hardware zoom is preferred when available.
  zoomLevel.value = 1.5
  softwareZoomFactor.value = 1
  await nextTick()

  if (!videoEl.value) {
    return
  }
  videoEl.value.srcObject = stream
  const onVideoReady = (): void => {
    webcamReady.value = true
    webcamError.value = null
    syncIntrinsicSize()
    if (videoTrack) {
      updateResolutionLabel(videoTrack)
    }
    applyZoomToTrack(zoomLevel.value)
    acquireWakeLock()
  }
  videoEl.value.onloadedmetadata = onVideoReady
  videoEl.value.onloadeddata = onVideoReady
  // Orientation change swaps videoWidth/videoHeight — the overlay viewBox must
  // follow or the orange rectangle lands in the wrong place.
  videoEl.value.onresize = syncIntrinsicSize
  if (videoEl.value.readyState >= 2) {
    onVideoReady()
  }
  try {
    await videoEl.value.play()
  } catch {
    /* autoplay can fail when the user hasn't gestured; ignored. */
  }
}

/**
 * Mirror the current video intrinsic size into the overlay viewBox refs.
 */
function syncIntrinsicSize(): void {
  const el = videoEl.value
  if (el?.videoWidth && el.videoHeight) {
    videoIntrinsicW.value = el.videoWidth
    videoIntrinsicH.value = el.videoHeight
  }
}

/**
 * The active camera track died (call, camera app, permission revoked).
 * Stop cleanly, tell the user, and try one automatic restart.
 */
function onCameraTrackEnded(): void {
  if (!webcamActive.value) {
    return
  }
  stopWebcam()
  webcamError.value = 'La caméra a été interrompue — reprise en cours…'
  window.setTimeout(() => {
    if (!webcamActive.value && liveCameraSupported.value && !document.hidden) {
      startWebcam(true)
    }
  }, 1_000)
}

async function startWebcam(preserveDeviceSelection = false): Promise<void> {
  if (webcamActive.value || webcamStarting.value) {
    return
  }
  unlockAudio()
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

/** Guard against two rapid camera switches racing each other. */
let cameraSwitching = false

async function onCameraChanged(deviceId: string | undefined): Promise<void> {
  if (!webcamActive.value || !deviceId || cameraSwitching) {
    return
  }
  cameraSwitching = true
  try {
    const picked = videoDevices.value.find((d) => d.id === deviceId)
    if (picked && isFrontCameraLabel(picked.label)) {
      toast.add({
        title: 'Caméra avant ignorée',
        description: 'Utilisez la caméra arrière pour scanner vos cartes.',
        color: 'warning',
      })
      selectedCameraId.value = pickRearCameraId(videoDevices.value)
    }
    stopWebcam()
    await startWebcam(true)
  } finally {
    cameraSwitching = false
  }
}

function stopWebcam(): void {
  if (webcamStream) {
    webcamStream.getTracks().forEach((t) => t.stop())
    webcamStream = null
  }
  if (videoTrack) {
    videoTrack.onended = null
  }
  videoTrack = null
  hardwareZoomCaps = null
  torchSupported.value = false
  torchOn.value = false
  if (videoEl.value) {
    videoEl.value.onloadedmetadata = null
    videoEl.value.onloadeddata = null
    videoEl.value.onresize = null
    videoEl.value.srcObject = null
  }
  webcamActive.value = false
  webcamReady.value = false
  webcamResolutionLabel.value = null
  zoomLevel.value = 1
  softwareZoomFactor.value = 1
  releaseWakeLock()
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
    await uploadPhoto(file, SCAN_LANGUAGE, undefined, WEBCAM_UPLOAD_COMPRESS, scanDirection.value)
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

// Every scan gets a visible outcome — a cash register that stays silent on a
// failed read is exactly what made the old page feel broken. Unidentified
// cards show as "À vérifier" rows and can still be bulk-cleared.
const displayedEvents = computed(() => events.value)

const counters = computed(() => {
  let added = 0
  let removed = 0
  let needs_review = 0
  let in_flight = 0
  for (const ev of displayedEvents.value) {
    if (ev.status === 'added') {
      added += 1
    } else if (ev.status === 'removed') {
      removed += 1
    } else if (ev.status === 'failed' || ev.status === 'needs_review' || ev.status === 'not_in_collection') {
      needs_review += 1
    } else {
      in_flight += 1
    }
  }
  return { total: displayedEvents.value.length, added, removed, needs_review, in_flight }
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
    case 'removed':
      return 'Retirée'
    case 'not_in_collection':
      return 'Absente de la collection'
    case 'dropped':
      return 'Ignorée'
    case 'failed':
      return 'Échec'
  }
}

function statusBadgeColor(s: ScanEventStatus): 'primary' | 'success' | 'warning' | 'error' | 'neutral' {
  switch (s) {
    case 'added':
      return 'success'
    case 'removed':
      return 'primary'
    case 'needs_review':
    case 'not_in_collection':
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

function canDismissScan(_s: ScanEventStatus): boolean {
  // Any scan can be removed from the feed, including ones still in
  // "OCR…" / "Identification…" — they just vanish from the list.
  return true
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
  if (s === 'removed') {
    return 'ring-primary/25 ring'
  }
  if (s === 'failed' || s === 'needs_review' || s === 'not_in_collection') {
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
    await uploadPhoto(file, SCAN_LANGUAGE, undefined, undefined, scanDirection.value)
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

// Audio feedback. The context must be created + resumed inside a user gesture
// (iOS keeps it `suspended` otherwise — the old beep was simply mute there).
let audioCtx: AudioContext | null = null

/**
 * Create / resume the AudioContext. Call from every user gesture that starts
 * a scan session (camera button, auto-scan switch, sound toggle).
 */
function unlockAudio(): void {
  if (typeof window === 'undefined') {
    return
  }
  try {
    const Ctx =
      window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!Ctx) {
      return
    }
    audioCtx = audioCtx ?? new Ctx()
    if (audioCtx.state === 'suspended') {
      audioCtx.resume()
    }
  } catch {
    /* audio is best-effort */
  }
}

/**
 * Play a short two-point sine sweep.
 * @param from - Start frequency (Hz).
 * @param to - End frequency (Hz).
 * @param volume - Peak gain.
 */
function playTone(from: number, to: number, volume: number): void {
  if (!soundOn.value || !audioCtx) {
    return
  }
  try {
    if (audioCtx.state === 'suspended') {
      audioCtx.resume()
    }
    const now = audioCtx.currentTime
    const osc = audioCtx.createOscillator()
    const gain = audioCtx.createGain()
    osc.type = 'sine'
    osc.frequency.setValueAtTime(from, now)
    osc.frequency.exponentialRampToValueAtTime(to, now + 0.12)
    gain.gain.setValueAtTime(0.0001, now)
    gain.gain.exponentialRampToValueAtTime(volume, now + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.22)
    osc.connect(gain).connect(audioCtx.destination)
    osc.start(now)
    osc.stop(now + 0.24)
  } catch {
    /* audio is best-effort */
  }
}

/** Rising "ding" — card added. */
function playBeep(): void {
  playTone(880, 1320, 0.25)
}

/** Falling "dong" — card removed (checkout). */
function playRemoveBeep(): void {
  playTone(660, 440, 0.25)
}

/** Low buzz — scan failed / needs review / rejected. */
function playErrorBeep(): void {
  playTone(300, 180, 0.3)
}

/**
 * Haptic feedback (Android Chrome; silently ignored elsewhere).
 * @param pattern - Vibration pattern in ms.
 */
function vibrate(pattern: number | number[]): void {
  try {
    navigator.vibrate?.(pattern)
  } catch {
    /* best-effort */
  }
}

/** Full-screen flash tint confirming the outcome without looking at the list. */
const flashKind = ref<'success' | 'removed' | 'error' | null>(null)
let flashTimer: ReturnType<typeof setTimeout> | null = null

/**
 * Trigger the outcome flash overlay for ~260 ms.
 * @param kind - Visual outcome family.
 */
function triggerFlash(kind: 'success' | 'removed' | 'error'): void {
  flashKind.value = kind
  if (flashTimer !== null) {
    clearTimeout(flashTimer)
  }
  flashTimer = setTimeout(() => {
    flashKind.value = null
    flashTimer = null
  }, 260)
}

/** Keep the phone screen awake during a scan session (best-effort). */
let wakeLock: { release: () => Promise<void> } | null = null

/**
 * Request a screen wake lock while the camera runs.
 */
async function acquireWakeLock(): Promise<void> {
  try {
    const wl = (navigator as Navigator & { wakeLock?: { request: (t: 'screen') => Promise<never> } }).wakeLock
    if (!wl || wakeLock) {
      return
    }
    wakeLock = (await wl.request('screen')) as unknown as { release: () => Promise<void> }
  } catch {
    wakeLock = null
  }
}

/**
 * Release the screen wake lock.
 */
function releaseWakeLock(): void {
  const held = wakeLock
  wakeLock = null
  if (held) {
    held.release().catch(() => undefined)
  }
}

/** Camera paused because the tab went to the background — resume on return. */
let resumeCameraOnVisible = false

/**
 * Background/foreground handling: iOS freezes the stream when the tab hides,
 * and the detector would then re-capture the same frozen frame on return.
 */
function onVisibilityChange(): void {
  if (document.hidden) {
    if (webcamActive.value) {
      resumeCameraOnVisible = true
      stopWebcam()
    }
    return
  }
  if (resumeCameraOnVisible && liveCameraSupported.value) {
    resumeCameraOnVisible = false
    startWebcam(true)
  }
}

/**
 * Upload the deskewed card the detector produced. The success chime is
 * triggered later, when the `added` event arrives and the info pop-up appears
 * — that's the moment the user actually wants to hear confirmation.
 */
async function onDetectorCapture(file: File): Promise<void> {
  uploading.value = true
  // A new card is being processed — drop the previous overlay right away so
  // the user sees we've moved on. The new card's overlay will appear when the
  // `added` event lands and the `latestAdded` watcher plays the chime.
  if (latestAdded.value) {
    dismissedAddedId.value = latestAdded.value.event_id
  }
  try {
    await uploadPhoto(file, SCAN_LANGUAGE, undefined, WEBCAM_UPLOAD_COMPRESS, scanDirection.value)
  } catch (err) {
    toast.add({ title: 'Envoi impossible', description: apiErrorMessage(err), color: 'error' })
  } finally {
    uploading.value = false
  }
}

// Cash-register auto-capture: OpenCV tracks the card outline; once it is held
// steady the deskewed crop is shot once, then re-arms when the card leaves.
const autoScanEnabled = computed(() => webcamActive.value && webcamReady.value && autoScan.value)
const {
  phase: autoScanPhase,
  quad: cardQuad,
  ready: detectorReady,
  loadError: detectorError,
} = useCardAutoScan({
  video: videoEl,
  enabled: autoScanEnabled,
  busy: uploading,
  onCapture: onDetectorCapture,
})

/**
 * The detector forces the quad to the card aspect ratio, so the 4 points form
 * a true rotated rectangle. Decompose them into {center, w, h, angle} so we
 * can draw a rounded `<rect>` — matches the competitor's clean look.
 */
const cardOverlay = computed<{
  cx: number
  cy: number
  w: number
  h: number
  angleDeg: number
} | null>(() => {
  const q = cardQuad.value
  if (!q) {
    return null
  }
  const cx = (q[0].x + q[1].x + q[2].x + q[3].x) / 4
  const cy = (q[0].y + q[1].y + q[2].y + q[3].y) / 4
  const topDx = q[1].x - q[0].x
  const topDy = q[1].y - q[0].y
  const botDx = q[2].x - q[3].x
  const botDy = q[2].y - q[3].y
  const w = (Math.hypot(topDx, topDy) + Math.hypot(botDx, botDy)) / 2
  const h = (Math.hypot(q[3].x - q[0].x, q[3].y - q[0].y) + Math.hypot(q[2].x - q[1].x, q[2].y - q[1].y)) / 2
  const angleDeg = (Math.atan2((topDy + botDy) / 2, (topDx + botDx) / 2) * 180) / Math.PI
  return { cx, cy, w, h, angleDeg }
})

/** Most recent settled card (added or removed), for the bottom info overlay. */
const dismissedAddedId = ref<string | null>(null)
const latestAdded = computed(() => {
  const ev = displayedEvents.value.find((e) => (e.status === 'added' || e.status === 'removed') && e.collection_card)
  if (!ev || ev.event_id === dismissedAddedId.value) {
    return null
  }
  return ev
})

/** One-line outcome text under the overlay card name. */
function outcomeLine(ev: ScanEvent): string {
  if (ev.status === 'removed') {
    if (ev.deleted) {
      return 'Retirée de ma collection (dernier exemplaire)'
    }
    return `Retirée de ma collection (reste ×${ev.remaining_quantity ?? '?'})`
  }
  return `Ajoutée à ma collection${ev.created === false && ev.collection_card ? ` (×${ev.collection_card.quantity})` : ''}`
}

// Sound + vibration + flash the moment each scan settles — the whole point of
// a cash register is to confirm without looking at the screen.
const notifiedOutcomeIds = new Set<string>()
watch(
  events,
  (list) => {
    for (const ev of list) {
      if (notifiedOutcomeIds.has(ev.event_id)) {
        continue
      }
      if (ev.status === 'added') {
        notifiedOutcomeIds.add(ev.event_id)
        playBeep()
        vibrate(60)
        triggerFlash('success')
      } else if (ev.status === 'removed') {
        notifiedOutcomeIds.add(ev.event_id)
        playRemoveBeep()
        vibrate([40, 60, 40])
        triggerFlash('removed')
      } else if (ev.status === 'needs_review' || ev.status === 'failed' || ev.status === 'not_in_collection') {
        notifiedOutcomeIds.add(ev.event_id)
        playErrorBeep()
        vibrate(220)
        triggerFlash('error')
      }
    }
    // The feed is capped: keep the notified set from growing forever.
    if (notifiedOutcomeIds.size > 300) {
      notifiedOutcomeIds.clear()
      for (const ev of list) {
        notifiedOutcomeIds.add(ev.event_id)
      }
    }
  },
  { deep: true },
)

// Server-side frame rejections (blurry, queue full…) are transient events —
// give an immediate "nothing happened" cue instead of silent dropping.
watch(lastDroppedEvent, (ev) => {
  if (!ev) {
    return
  }
  // Debounce drops are expected with capture bursts — stay quiet on those.
  if (ev.drop_reason === 'debounce') {
    return
  }
  playErrorBeep()
  vibrate(120)
  triggerFlash('error')
  toast.add({
    title: 'Photo ignorée',
    description: ev.error ?? 'Le serveur a rejeté cette photo.',
    color: 'warning',
  })
})

const autoScanStatus = computed<{ label: string; color: 'primary' | 'success' | 'neutral' }>(() => {
  if (detectorError.value) {
    return { label: 'Moteur de scan indisponible', color: 'neutral' }
  }
  if (!detectorReady.value) {
    return { label: 'Chargement du moteur de scan…', color: 'primary' }
  }
  if (uploading.value) {
    return { label: 'Envoi…', color: 'primary' }
  }
  switch (autoScanPhase.value) {
    case 'watching':
      return { label: 'Placez ou passez une carte', color: 'neutral' }
    case 'settling':
      return { label: 'Lecture en cours…', color: 'primary' }
    case 'captured':
      return { label: 'Carte capturée', color: 'success' }
    case 'cooldown':
      return { label: 'Retirez la carte pour la suivante', color: 'success' }
    default:
      return { label: 'Caméra en pause', color: 'neutral' }
  }
})

// Sound / auto-scan toggles happen inside a tap: unlock audio right there so
// the confirmation beep is audible on iOS (context stays suspended otherwise).
watch(autoScan, (): void => {
  unlockAudio()
})
watch(soundOn, (on: boolean): void => {
  if (on) {
    unlockAudio()
  }
})

onMounted(async () => {
  document.addEventListener('visibilitychange', onVisibilityChange)
  await refreshRecent()
  await connect()
  // Desktop is a monitor screen (QR + live feed) — no camera to open there.
  if (!isDesktopApp.value && liveCameraSupported.value) {
    await startWebcam()
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', onVisibilityChange)
  stopWebcam()
  disconnect()
  if (flashTimer !== null) {
    clearTimeout(flashTimer)
    flashTimer = null
  }
  if (audioCtx) {
    audioCtx.close().catch(() => undefined)
    audioCtx = null
  }
})
</script>
