<script setup lang="ts">
definePageMeta({ middleware: 'auth' })

const route = useRoute()
const { getVintedBatchActive } = useArticles()
const batchStream = useVintedBatchStream()
const publishStream = useVintedPublishStream()

/** ``batch`` | ``single`` | ``none`` (idle / chargement initial) */
const streamMode = ref<'none' | 'batch' | 'single'>('none')

const logScrollEl = ref<HTMLElement | null>(null)

const activeLogEntries = computed(() => {
  if (streamMode.value === 'single') {
    return publishStream.logEntries.value
  }
  if (streamMode.value === 'batch') {
    return batchStream.logEntries.value
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
/** Flux article unique : ``followStream`` s'est terminé sans erreur réseau. */
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

async function connectSingleArticle(articleId: number) {
  idleMessage.value = null
  streamError.value = null
  singleFinished.value = false
  loading.value = true
  streamMode.value = 'single'
  batchStream.closeBatchStream()
  publishStream.closeStream()
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
  const jobId = typeof qJob === 'string' ? qJob.trim() : ''
  const articleIdRaw = typeof qArticle === 'string' ? qArticle.trim() : ''
  const articleId = articleIdRaw ? Number.parseInt(articleIdRaw, 10) : NaN

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
        'Aucune publication en cours. Lancez une mise en ligne depuis la liste d’articles ou créez un article avec publication Vinted, puis ouvrez à nouveau ce journal (vous serez redirigé automatiquement).'
    }
  } catch {
    idleMessage.value = 'Impossible de récupérer l’état du lot (réseau ou session).'
  } finally {
    loading.value = false
  }
}

onMounted(bootstrap)

watch(
  () => [route.query.job, route.query.article],
  () => {
    bootstrap()
  }
)

onBeforeUnmount(() => {
  batchStream.closeBatchStream()
  publishStream.closeStream()
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
      <UDashboardNavbar title="Journal publication Vinted">
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
        />

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
              Connexion au flux de publication (article unique)…
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
                <UBadge v-if="finished || singleFinished" color="success" variant="subtle">
                  Terminé
                </UBadge>
                <UBadge
                  v-else-if="streamMode === 'single' && !loading"
                  color="neutral"
                  variant="subtle"
                >
                  Article unique
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
                    v-if="entry.screenshot"
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
