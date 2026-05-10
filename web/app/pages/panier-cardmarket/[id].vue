<template>
  <UDashboardPanel :id="`panier-cardmarket-${searchId}`">
    <template #header>
      <UDashboardNavbar :title="detail?.name || 'Panier Cardmarket'">
        <template #leading>
          <UButton to="/panier-cardmarket" color="neutral" variant="ghost" icon="i-lucide-arrow-left" />
        </template>
        <template #right>
          <div class="flex items-center gap-2">
            <UButton
              v-if="running"
              color="error"
              variant="soft"
              icon="i-lucide-square"
              :loading="cancelling"
              @click="onCancel"
            >
              Arrêter l’analyse
            </UButton>
            <UButton
              color="primary"
              icon="i-lucide-play"
              :loading="running"
              :disabled="!isDesktopApp || !detail || running"
              @click="onRun"
            >
              Lancer l’analyse
            </UButton>
          </div>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="space-y-6 px-4 py-6 sm:px-6 sm:py-8">
        <UAlert
          v-if="!isDesktopApp"
          color="warning"
          variant="subtle"
          icon="i-lucide-monitor-down"
          title="Application bureau requise"
          description="Installez ou ouvrez GoupixDex desktop pour exécuter l’analyse Cardmarket (Chrome + nodriver)."
        />

        <GoupixDexCardmarketSessionBanner v-if="isDesktopApp" :session="cmSession" :loading="cmSessionLoading" />

        <UAlert
          v-if="pageError"
          color="error"
          variant="subtle"
          icon="i-lucide-alert-triangle"
          title="Erreur"
          :description="pageError"
        />

        <UAlert
          v-if="cloudflareWaiting"
          color="warning"
          variant="subtle"
          icon="i-lucide-shield-alert"
          title="Vérification Cloudflare requise"
          :description="cloudflareMessage"
        >
          <template #actions>
            <p v-if="cloudflareUrl" class="text-muted text-xs break-all">URL : {{ cloudflareUrl }}</p>
          </template>
        </UAlert>

        <template v-if="detail">
          <UCard class="ring-default/60 shadow-sm ring-1">
            <template #header>
              <p class="text-highlighted font-medium">Configuration</p>
            </template>
            <div class="space-y-4 p-4 sm:p-6">
              <UFormField label="Nom">
                <UInput v-model="editName" class="max-w-xl" />
              </UFormField>
              <UFormField
                label="Liens Cardmarket"
                :hint="editDetectedHint"
                help="Collez vos liens en bloc — GoupixDex accepte les séparateurs newline / tab / espace / virgule et déduplique automatiquement."
              >
                <UTextarea
                  v-model="editUrlsText"
                  :rows="12"
                  autoresize
                  class="w-full font-mono text-xs"
                  placeholder="https://www.cardmarket.com/fr/Pokemon/Products/Singles/...&#10;https://www.cardmarket.com/fr/Pokemon/Products/Singles/..."
                />
              </UFormField>
              <div class="flex flex-wrap gap-2">
                <UButton
                  color="primary"
                  :loading="saving"
                  :disabled="running || !editDetectedUrls.length"
                  @click="onSave"
                >
                  Enregistrer
                </UButton>
                <UButton
                  v-if="editUrlsText && editUrlsText !== normalizedUrlsText"
                  color="neutral"
                  variant="ghost"
                  :disabled="running"
                  @click="normalizeUrlsText"
                >
                  Nettoyer la liste
                </UButton>
              </div>
            </div>
          </UCard>

          <UCard v-if="running || logLines.length" class="ring-default/60 shadow-sm ring-1">
            <template #header>
              <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div class="flex items-center gap-2">
                  <p class="text-highlighted font-medium">Progression</p>
                  <UBadge v-if="cloudflareWaiting" color="warning" variant="subtle" size="sm">
                    En attente Cloudflare
                  </UBadge>
                  <UBadge v-else-if="running && livePartialResult" color="primary" variant="subtle" size="sm">
                    Aperçu en direct
                  </UBadge>
                </div>
                <span v-if="progressTotal" class="text-muted text-xs tabular-nums">
                  Carte {{ progressCurrent }} / {{ progressTotal }}
                </span>
              </div>
            </template>
            <div class="space-y-3 p-4 sm:p-6">
              <UProgress v-if="running && progressTotal" :model-value="progressPercent" size="sm" />
              <pre
                ref="logEl"
                class="border-default bg-elevated/40 max-h-64 overflow-auto rounded-lg border p-3 font-mono text-xs whitespace-pre-wrap"
                >{{ logLines.join('\n') }}</pre
              >
            </div>
          </UCard>

          <template v-if="lastResult">
            <p v-if="running && livePartialResult" class="text-muted text-xs">
              Aperçu en direct (mêmes filtres que la liste finale) — cet aperçu est remplacé par le résultat définitif
              lorsque l’analyse est terminée.
            </p>
            <div class="grid gap-6 lg:grid-cols-2">
              <UCard class="ring-default/60 shadow-sm ring-1">
                <template #header>
                  <p class="text-highlighted font-medium">Top vendeurs (couverture)</p>
                  <p class="text-muted text-xs">≥ 2 cartes — tri : nombre de cartes puis total €</p>
                </template>
                <div class="divide-default max-h-[32rem] divide-y overflow-y-auto">
                  <div v-for="(row, i) in coverageRows" :key="`cov-${i}`" class="px-4 py-3 sm:px-5">
                    <GoupixDexCardmarketSellerBlock :row="row" />
                  </div>
                  <div v-if="!coverageRows.length" class="text-muted px-4 py-6 text-center text-xs">
                    Pas encore de vendeur couvrant ≥ 2 cartes.
                  </div>
                </div>
              </UCard>
              <UCard class="ring-default/60 shadow-sm ring-1">
                <template #header>
                  <p class="text-highlighted font-medium">Top vendeurs (surcoût vs min)</p>
                  <p class="text-muted text-xs">≥ 2 cartes — tri : % surcoût total puis nombre de cartes</p>
                </template>
                <div class="divide-default max-h-[32rem] divide-y overflow-y-auto">
                  <div v-for="(row, i) in valueRows" :key="`val-${i}`" class="px-4 py-3 sm:px-5">
                    <GoupixDexCardmarketSellerBlock :row="row" />
                  </div>
                  <div v-if="!valueRows.length" class="text-muted px-4 py-6 text-center text-xs">
                    Pas encore de comparaison surcoût disponible.
                  </div>
                </div>
              </UCard>
            </div>

            <UCard v-if="missingCards.length" class="ring-default/60 shadow-sm ring-1">
              <template #header>
                <p class="text-highlighted font-medium">Sans offre (filtres)</p>
              </template>
              <ul class="text-muted list-disc space-y-1 px-6 py-4 text-sm">
                <li v-for="c in missingCards" :key="c">{{ c }}</li>
              </ul>
            </UCard>
          </template>
        </template>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { Ref } from 'vue'
import type { CardmarketSearchDetail, CardmarketSearchProgressPayload } from '~/types/CardmarketSearch'
import type { CardmarketSessionResponse } from '~/types/CardmarketSession'

definePageMeta({ middleware: 'auth' })

const route = useRoute()
const toast = useToast()
const { getSearch, updateSearch, runWithProgress, cancelLocalRun, isDesktopApp } = useCardmarketSearches()
const { fetchSession: fetchCmSession } = useCardmarketWorker()

const cmSession: Ref<CardmarketSessionResponse | null> = ref(null)
const cmSessionLoading: Ref<boolean> = ref(false)

async function loadCardmarketSession(): Promise<void> {
  if (!isDesktopApp.value) {
    cmSession.value = null
    return
  }
  cmSessionLoading.value = true
  try {
    cmSession.value = await fetchCmSession()
  } catch {
    cmSession.value = null
  } finally {
    cmSessionLoading.value = false
  }
}

const searchId = computed(() => Number(route.params.id))
const detail: Ref<CardmarketSearchDetail | null> = ref(null)
const pageError: Ref<string | null> = ref(null)

const editName: Ref<string> = ref('')
const editUrlsText: Ref<string> = ref('')
const saving: Ref<boolean> = ref(false)

const running: Ref<boolean> = ref(false)
const cancelling: Ref<boolean> = ref(false)
const logLines: Ref<string[]> = ref([])
const logEl = ref<HTMLElement | null>(null)
const progressCurrent: Ref<number> = ref(0)
const progressTotal: Ref<number> = ref(0)

const cloudflareWaiting: Ref<boolean> = ref(false)
const cloudflareUrl: Ref<string | null> = ref(null)
const cloudflareMessage: Ref<string> = ref('')

const livePartialResult: Ref<Record<string, unknown> | null> = ref(null)

const progressPercent = computed(() => {
  if (!progressTotal.value) {
    return 0
  }
  return Math.min(100, Math.round((progressCurrent.value / progressTotal.value) * 100))
})

const lastResult = computed<Record<string, unknown> | null>(() => {
  if (livePartialResult.value) {
    return livePartialResult.value
  }
  return (detail.value?.last_result ?? null) as Record<string, unknown> | null
})

const coverageRows = computed(() => {
  const r = lastResult.value
  if (!r || !Array.isArray(r.seller_summary_coverage)) {
    return []
  }
  return (r.seller_summary_coverage as Record<string, unknown>[]).slice(0, 25)
})

const valueRows = computed(() => {
  const r = lastResult.value
  if (!r || !Array.isArray(r.seller_summary_value)) {
    return []
  }
  return (r.seller_summary_value as Record<string, unknown>[]).slice(0, 25)
})

const missingCards = computed(() => {
  const r = lastResult.value
  if (!r || !Array.isArray(r.cards)) {
    return []
  }
  const out: string[] = []
  for (const c of r.cards as Record<string, unknown>[]) {
    const offers = c.offers as unknown[] | undefined
    const code = String(c.code || '')
    if (!code) {
      continue
    }
    if (!offers || offers.length === 0) {
      out.push(code)
    }
  }
  return out
})

async function loadDetail(): Promise<void> {
  pageError.value = null
  try {
    const d = await getSearch(searchId.value)
    detail.value = d
    editName.value = d.name || ''
    editUrlsText.value = (d.urls || []).map((u) => u.url).join('\n')
  } catch (e: unknown) {
    pageError.value = apiErrorMessage(e)
  }
}

const editDetectedUrls = computed(() => parseCardmarketUrlsFromText(editUrlsText.value))

const normalizedUrlsText = computed(() => editDetectedUrls.value.join('\n'))

const editDetectedHint = computed(() => {
  const n = editDetectedUrls.value.length
  if (!n) {
    return 'Aucun lien détecté'
  }
  return `${n} lien${n > 1 ? 's' : ''} détecté${n > 1 ? 's' : ''}`
})

function normalizeUrlsText(): void {
  editUrlsText.value = normalizedUrlsText.value
}

async function onSave(): Promise<void> {
  if (!detail.value) {
    return
  }
  const urls = editDetectedUrls.value
  if (!urls.length) {
    toast.add({ title: 'Au moins une URL Cardmarket requise', color: 'warning' })
    return
  }
  saving.value = true
  try {
    const name = editName.value.trim() || null
    detail.value = await updateSearch(detail.value.id, { name, urls })
    editUrlsText.value = (detail.value.urls || []).map((u) => u.url).join('\n')
    toast.add({
      title: 'Enregistré',
      description: `${urls.length} lien${urls.length > 1 ? 's' : ''}.`,
      color: 'success',
    })
  } catch (e: unknown) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  } finally {
    saving.value = false
  }
}

let wsCleanup: (() => void) | null = null

function appendLog(line: string): void {
  logLines.value = [...logLines.value, line]
  void nextTick((): void => {
    const el = logEl.value
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  })
}

function resetCloudflareBanner(): void {
  cloudflareWaiting.value = false
  cloudflareUrl.value = null
  cloudflareMessage.value = ''
}

function finalizeRun(): void {
  running.value = false
  cancelling.value = false
  resetCloudflareBanner()
  wsCleanup?.()
  wsCleanup = null
}

function handleProgressPayload(p: CardmarketSearchProgressPayload): void {
  if (p.type === 'log' && typeof p.message === 'string') {
    appendLog(p.message)
    return
  }
  if (p.type === 'progress') {
    if (typeof p.current === 'number') {
      progressCurrent.value = p.current
    }
    if (typeof p.total === 'number') {
      progressTotal.value = p.total
    }
    const code = typeof p.code === 'string' ? p.code : ''
    appendLog(`→ ${p.current ?? '?'}/${p.total ?? '?'} ${code}`)
    return
  }
  if (p.type === 'partial' && p.payload && typeof p.payload === 'object') {
    livePartialResult.value = p.payload as Record<string, unknown>
    return
  }
  if (p.type === 'cloudflare_wait') {
    cloudflareWaiting.value = true
    cloudflareUrl.value = (p.url as string) || null
    cloudflareMessage.value =
      typeof p.message === 'string' && p.message
        ? p.message
        : 'Cloudflare demande une vérification — cochez la case dans la fenêtre Chrome ouverte par GoupixDex.'
    appendLog(`⚠ Cloudflare — vérification manuelle requise${p.url ? ` (${p.url})` : ''}`)
    return
  }
  if (p.type === 'cloudflare_resolved') {
    appendLog('✓ Cloudflare résolu, reprise…')
    resetCloudflareBanner()
    return
  }
  if (p.type === 'cloudflare_timeout') {
    appendLog('✗ Cloudflare non résolu dans les temps.')
    resetCloudflareBanner()
    return
  }
  if (p.type === 'error') {
    appendLog(`ERREUR: ${String(p.message ?? '')}`)
    finalizeRun()
    toast.add({ title: 'Analyse interrompue', description: String(p.message ?? ''), color: 'error' })
    void loadDetail()
    return
  }
  if (p.type === 'cancelled') {
    appendLog('■ Analyse arrêtée.')
    finalizeRun()
    toast.add({ title: 'Analyse arrêtée', description: String(p.message ?? ''), color: 'warning' })
    void loadDetail()
    return
  }
  if (p.type === 'done') {
    appendLog('Terminé.')
    finalizeRun()
    livePartialResult.value = null
    void loadDetail()
    toast.add({ title: 'Analyse terminée', color: 'success' })
  }
}

async function onRun(): Promise<void> {
  if (!detail.value || !isDesktopApp.value) {
    return
  }
  running.value = true
  cancelling.value = false
  logLines.value = []
  progressCurrent.value = 0
  progressTotal.value = 0
  livePartialResult.value = null
  resetCloudflareBanner()
  try {
    const { close } = await runWithProgress(detail.value.id, handleProgressPayload)
    wsCleanup = close
  } catch (e: unknown) {
    running.value = false
    toast.add({ title: 'Lancement impossible', description: apiErrorMessage(e), color: 'error' })
  }
}

async function onCancel(): Promise<void> {
  if (!detail.value || !running.value || cancelling.value) {
    return
  }
  cancelling.value = true
  try {
    await cancelLocalRun(detail.value.id)
    appendLog('Demande d’arrêt envoyée…')
  } catch (e: unknown) {
    cancelling.value = false
    toast.add({ title: 'Arrêt impossible', description: apiErrorMessage(e), color: 'error' })
  }
}

useGoupixPageSeo('Panier Cardmarket', 'Détail d’un panier Cardmarket et analyse des vendeurs.')

onMounted((): void => {
  void loadDetail()
  void loadCardmarketSession()
})

watch(isDesktopApp, (desktop) => {
  if (desktop) {
    void loadCardmarketSession()
  } else {
    cmSession.value = null
  }
})

onBeforeUnmount((): void => {
  wsCleanup?.()
  wsCleanup = null
})

watch(searchId, (): void => {
  void loadDetail()
})
</script>
