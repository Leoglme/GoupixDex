<script setup lang="ts">
import { WARDROBE_IMPORT_STORAGE_KEY } from '~/composables/useWardrobeImportPrefill'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Journal des publications',
  "Suivez en direct la mise en ligne Vinted (captures) et eBay (étapes API) dans GoupixDex, sur le web ou l'application desktop."
)

const route = useRoute()
const { getVintedBatchActive } = useArticles()
const batchStream = useVintedBatchStream()
const publishStream = useVintedPublishStream()
const wardrobeStream = useWardrobeSyncStream()
const { isDesktopApp } = useDesktopRuntime()

/** ``batch`` | ``single`` | ``wardrobe`` | ``none`` (idle / initial load) */
const streamMode = ref<'none' | 'batch' | 'single' | 'wardrobe'>('none')

const navbarTitle = computed(() =>
  streamMode.value === 'wardrobe' ? 'Journal import Vinted' : 'Journal des publications'
)

const logScrollEl = ref<HTMLElement | null>(null)

const activeLogEntries = computed(() => {
  if (streamMode.value === 'single') {
    return publishStream.logEntries.value
  }
  if (streamMode.value === 'batch') {
    return batchStream.logEntries.value
  }
  if (streamMode.value === 'wardrobe') {
    return wardrobeStream.logEntries.value
  }
  return []
})

watch(
  activeLogEntries,
  async () => {
    await nextTick()
    const el = logScrollEl.value
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  },
  { deep: true }
)

const loading = ref(false)
const idleMessage = ref<string | null>(null)
const streamError = ref<string | null>(null)

const progress = computed(() =>
  streamMode.value === 'batch' ? batchStream.progress.value : null
)
const finished = computed(() =>
  streamMode.value === 'batch' ? batchStream.finished.value : false
)
/** Wardrobe stream: finished before redirect to batch create. */
const wardrobeFinished = ref(false)
/** Single-article stream: ``followStream`` ended without a network error. */
const singleFinished = ref(false)
const lastSummary = computed(() =>
  streamMode.value === 'batch' ? batchStream.lastSummary.value : null
)

const progressPercent = computed(() => {
  const p = progress.value
  if (!p || !p.total) {
    return 0
  }
  return Math.min(100, Math.round((100 * p.current) / p.total))
})

const progressLabel = computed(() => {
  const p = progress.value
  if (!p || !p.total) {
    return null
  }
  const title = p.title ? ` — ${p.title}` : ''
  return `Annonce ${p.current} / ${p.total}${title}`
})

const showMainPanels = computed(
  () => !(idleMessage.value && !loading.value)
)

async function connectBatchJob(jobId: string) {
  idleMessage.value = null
  streamError.value = null
  singleFinished.value = false
  loading.value = true
  streamMode.value = 'batch'
  batchStream.closeBatchStream()
  publishStream.closeStream()
  wardrobeStream.closeStream()
  try {
    await batchStream.followBatchStream(`/articles/vinted-batch/${jobId}/stream`, {
      quiet: true
    })
  } catch (e) {
    streamError.value = e instanceof Error ? e.message : 'Flux interrompu'
  } finally {
    loading.value = false
  }
}

async function connectWardrobeJob(jobId: string) {
  idleMessage.value = null
  streamError.value = null
  singleFinished.value = false
  wardrobeFinished.value = false
  loading.value = true
  streamMode.value = 'wardrobe'
  batchStream.closeBatchStream()
  publishStream.closeStream()
  wardrobeStream.closeStream()
  try {
    const result = await wardrobeStream.followJobStream(jobId)
    sessionStorage.setItem(WARDROBE_IMPORT_STORAGE_KEY, JSON.stringify({ result }))
    wardrobeFinished.value = true
    await navigateTo({ path: '/articles/batch-create', query: { from: 'wardrobe' } })
  } catch (e) {
    streamError.value = e instanceof Error ? e.message : 'Flux interrompu'
  } finally {
    loading.value = false
  }
}

async function connectSingleArticle(articleId: number) {
  idleMessage.value = null
  streamError.value = null
  singleFinished.value = false
  loading.value = true
  streamMode.value = 'single'
  batchStream.closeBatchStream()
  publishStream.closeStream()
  wardrobeStream.closeStream()
  try {
    await publishStream.followStream(`/articles/${articleId}/vinted-progress`, 'logs')
    singleFinished.value = true
  } catch (e) {
    streamError.value = e instanceof Error ? e.message : 'Flux interrompu'
  } finally {
    loading.value = false
  }
}

async function bootstrap() {
  const qJob = route.query.job
  const qArticle = route.query.article
  const qWardrobe = route.query.wardrobe_job
  const jobId = typeof qJob === 'string' ? qJob.trim() : ''
  const wardrobeJobId = typeof qWardrobe === 'string' ? qWardrobe.trim() : ''
  const articleIdRaw = typeof qArticle === 'string' ? qArticle.trim() : ''
  const articleId = articleIdRaw ? Number.parseInt(articleIdRaw, 10) : NaN

  if (wardrobeJobId) {
    if (!isDesktopApp.value) {
      loading.value = false
      streamMode.value = 'none'
      idleMessage.value =
        "L'import garde-robe Vinted nécessite l'application desktop (navigateur local sur votre machine)."
      return
    }
    await connectWardrobeJob(wardrobeJobId)
    return
  }
  if (jobId) {
    await connectBatchJob(jobId)
    return
  }
  if (Number.isFinite(articleId) && articleId > 0) {
    await connectSingleArticle(articleId)
    return
  }

  loading.value = true
  idleMessage.value = null
  streamMode.value = 'none'
  singleFinished.value = false
  try {
    const active = await getVintedBatchActive()
    if (active.job_id) {
      await connectBatchJob(active.job_id)
    } else {
      idleMessage.value =
        "Aucune publication en cours. Lancez une mise en ligne eBay ou Vinted depuis la liste ou la création d'article — vous serez redirigé ici automatiquement — ou ouvrez ce journal avec ?article=ID."
    }
  } catch {
    idleMessage.value = "Impossible de récupérer l'état du lot (réseau ou session)."
  } finally {
    loading.value = false
  }
}

onMounted(bootstrap)

watch(
  () => [route.query.job, route.query.article, route.query.wardrobe_job],
  () => {
    bootstrap()
  }
)

onBeforeUnmount(() => {
  batchStream.closeBatchStream()
  publishStream.closeStream()
  wardrobeStream.closeStream()
})
</script>

<template>
  <UDashboardPanel
    id="vinted-logs"
    class="flex min-h-0 flex-1 flex-col"
    :ui="{
      root: 'flex min-h-0 flex-1 flex-col',
      body: 'flex min-h-0 flex-1 flex-col overflow-hidden p-0'
    }"
  >
    <template #header>
      <UDashboardNavbar :title="navbarTitle">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton to="/articles" color="neutral" variant="ghost" icon="i-lucide-list">
            Articles
          </UButton>
          <UButton
            to="/articles/batch-create"
            color="neutral"
            variant="subtle"
            icon="i-lucide-layers"
          >
            Création groupée
          </UButton>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div
        class="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden p-4 sm:p-6 lg:min-h-[calc(100dvh-7rem)]"
      >
        <UAlert
          v-if="idleMessage && !loading"
          color="neutral"
          variant="subtle"
          icon="i-lucide-info"
          :title="idleMessage"
        >
          <template #description>
            <span v-if="!isDesktopApp" class="text-sm text-muted">
              Pour l'import garde-robe ou certains lots Vinted, installez aussi
              <NuxtLink to="/downloads" class="underline underline-offset-2">
                l'application desktop
              </NuxtLink>
              .
            </span>
          </template>
        </UAlert>

        <UAlert
          v-if="streamError"
          color="error"
          variant="subtle"
          icon="i-lucide-alert-circle"
          :title="streamError"
        />

        <div
          v-if="showMainPanels"
          class="grid min-h-0 flex-1 gap-4 [grid-template-rows:minmax(0,auto)_minmax(0,1fr)]"
        >
          <UCard
            v-if="streamMode === 'batch'"
            class="flex min-h-0 flex-col overflow-hidden"
            :ui="{
              root: 'flex min-h-0 flex-col overflow-hidden',
              header: 'shrink-0',
              body: 'flex min-h-0 flex-1 flex-col justify-center gap-3'
            }"
          >
            <template #header>
              <div class="flex flex-wrap items-center justify-between gap-2">
                <span class="font-medium text-highlighted">Progression (lot)</span>
                <span v-if="progressLabel" class="text-sm text-muted">{{ progressLabel }}</span>
              </div>
            </template>

            <UProgress
              v-if="progress && progress.total > 0"
              :model-value="progress.current"
              :max="progress.total"
              status
              size="lg"
              class="w-full"
            />
            <UProgress
              v-else-if="loading"
              size="md"
              class="w-full"
              animation="carousel"
            />
            <p
              v-if="progress && progress.total > 0"
              class="text-center text-xs text-muted"
            >
              {{ progressPercent }}&nbsp;% de la série
            </p>
            <p
              v-else-if="loading"
              class="text-center text-xs text-muted"
            >
              Connexion au flux…
            </p>
          </UCard>

          <UCard
            v-else-if="streamMode === 'single' && loading"
            class="shrink-0"
            :ui="{ body: 'py-3' }"
          >
            <p class="text-center text-sm text-muted">
              Connexion au flux de publication (Vinted et/ou eBay)…
            </p>
            <UProgress size="md" class="mt-2 w-full" animation="carousel" />
          </UCard>

          <UCard
            v-else-if="streamMode === 'wardrobe' && loading"
            class="shrink-0"
            :ui="{ body: 'py-3' }"
          >
            <p class="text-center text-sm text-muted">
              Synchronisation garde-robe Vinted (connexion Chrome, catalogue)…
            </p>
            <UProgress size="md" class="mt-2 w-full" animation="carousel" />
          </UCard>

          <UCard
            class="flex min-h-[12rem] flex-1 flex-col overflow-hidden"
            :ui="{
              root: 'flex min-h-0 flex-1 flex-col overflow-hidden',
              header: 'shrink-0',
              body: 'flex min-h-0 flex-1 flex-col overflow-hidden p-0'
            }"
          >
            <template #header>
              <div class="flex flex-wrap items-center gap-2">
                <span class="font-medium text-highlighted">Journal serveur</span>
                <UBadge v-if="finished || singleFinished || wardrobeFinished" color="success" variant="subtle">
                  Terminé
                </UBadge>
                <UBadge
                  v-else-if="streamMode === 'wardrobe' && !loading"
                  color="neutral"
                  variant="subtle"
                >
                  Import garde-robe
                </UBadge>
                <UBadge
                  v-else-if="streamMode === 'single' && !loading"
                  color="neutral"
                  variant="subtle"
                >
                  Article (Vinted / eBay)
                </UBadge>
                <UIcon
                  v-if="loading"
                  name="i-lucide-loader-2"
                  class="size-4 animate-spin text-primary"
                />
              </div>
            </template>

            <div
              ref="logScrollEl"
              class="min-h-0 flex-1 overflow-y-auto px-4 py-3 sm:px-5"
            >
              <ul class="space-y-4">
                <li v-if="!activeLogEntries.length && loading" class="text-sm text-muted">
                  Connexion au flux…
                </li>
                <li
                  v-for="(entry, i) in activeLogEntries"
                  :key="i"
                  class="space-y-2 border-b border-default/40 pb-4 last:border-0"
                >
                  <p class="break-words font-mono text-sm text-muted">
                    {{ entry.text }}
                  </p>
                  <img
                    v-if="'screenshot' in entry && typeof entry.screenshot === 'string'"
                    :src="entry.screenshot"
                    alt="Capture navigateur Vinted"
                    class="max-h-64 max-w-full rounded-lg border border-default/60 object-contain object-top shadow-sm ring-1 ring-default/30"
                    loading="lazy"
                  >
                </li>
              </ul>
            </div>
          </UCard>
        </div>

        <UCard
          v-if="lastSummary && typeof lastSummary === 'object' && streamMode === 'batch'"
          class="shrink-0"
          :ui="{ body: 'p-0' }"
        >
          <template #header>
            <span class="font-medium text-highlighted">Résumé technique (JSON)</span>
          </template>
          <pre
            class="max-h-64 overflow-auto rounded-md bg-elevated/50 p-3 text-xs ring ring-default m-4 mt-0"
          >{{ JSON.stringify(lastSummary, null, 2) }}</pre>
        </UCard>
      </div>
    </template>
  </UDashboardPanel>
</template>
