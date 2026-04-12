<script setup lang="ts">
import type { AccordionItem } from '@nuxt/ui'

definePageMeta({ middleware: 'auth' })

const route = useRoute()
const { getVintedBatchActive } = useArticles()
const batchStream = useVintedBatchStream()
const logEl = batchStream.logEl
const progress = batchStream.progress
const logs = batchStream.logs
const finished = batchStream.finished
const lastSummary = batchStream.lastSummary

const loading = ref(false)
const idleMessage = ref<string | null>(null)
const streamError = ref<string | null>(null)

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

/** Affiche la zone progression + logs (masquée uniquement si aucun job et message d’attente). */
const showMainPanels = computed(
  () => !(idleMessage.value && !loading.value)
)

const summaryAccordionItems = computed<AccordionItem[]>(() => [
  {
    label: 'Résumé technique (JSON)',
    icon: 'i-lucide-braces',
    value: 'json',
    content: ''
  }
])

async function connectToJob(jobId: string) {
  idleMessage.value = null
  streamError.value = null
  loading.value = true
  batchStream.closeBatchStream()
  try {
    await batchStream.followBatchStream(`/articles/vinted-batch/${jobId}/stream`)
  } catch (e) {
    streamError.value = e instanceof Error ? e.message : 'Flux interrompu'
  } finally {
    loading.value = false
  }
}

async function bootstrap() {
  const q = route.query.job
  const fromQuery = typeof q === 'string' ? q.trim() : ''
  if (fromQuery) {
    await connectToJob(fromQuery)
    return
  }
  loading.value = true
  idleMessage.value = null
  try {
    const active = await getVintedBatchActive()
    if (active.job_id) {
      await connectToJob(active.job_id)
    } else {
      idleMessage.value =
        'Aucun lot Vinted actif. Lancez une création groupée avec l’option Vinted, ou attendez qu’une tâche soit démarrée.'
    }
  } catch {
    idleMessage.value = 'Impossible de récupérer l’état du lot (réseau ou session).'
  } finally {
    loading.value = false
  }
}

onMounted(bootstrap)

onBeforeUnmount(() => {
  batchStream.closeBatchStream()
})
</script>

<template>
  <UDashboardPanel
    id="vinted-batch-logs"
    class="flex min-h-0 flex-1 flex-col"
    :ui="{
      root: 'flex min-h-0 flex-1 flex-col',
      body: 'flex min-h-0 flex-1 flex-col overflow-hidden p-0'
    }"
  >
    <template #header>
      <UDashboardNavbar title="Journal publication Vinted (lot)">
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
          class="grid min-h-0 flex-1 gap-4 [grid-template-rows:minmax(0,1fr)_minmax(0,1fr)]"
        >
          <UCard
            class="flex min-h-0 flex-col overflow-hidden"
            :ui="{
              root: 'flex min-h-0 flex-col overflow-hidden',
              header: 'shrink-0',
              body: 'flex min-h-0 flex-1 flex-col justify-center gap-3'
            }"
          >
            <template #header>
              <div class="flex flex-wrap items-center justify-between gap-2">
                <span class="font-medium text-highlighted">Progression</span>
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
              Connexion au flux ou attente de la progression…
            </p>
          </UCard>

          <UCard
            class="flex min-h-0 flex-col overflow-hidden"
            :ui="{
              root: 'flex min-h-0 flex-col overflow-hidden',
              header: 'shrink-0',
              body: 'flex min-h-0 flex-1 flex-col overflow-hidden p-0'
            }"
          >
            <template #header>
              <div class="flex flex-wrap items-center gap-2">
                <span class="font-medium text-highlighted">Journal serveur</span>
                <UBadge v-if="finished" color="success" variant="subtle">
                  Terminé
                </UBadge>
                <UIcon
                  v-if="loading"
                  name="i-lucide-loader-2"
                  class="size-4 animate-spin text-primary"
                />
              </div>
            </template>

            <div
              ref="logEl"
              class="min-h-0 flex-1 overflow-y-auto px-4 py-3 font-mono text-sm sm:px-5"
            >
              <ul class="space-y-1">
                <li v-if="!logs.length && loading" class="text-muted">
                  Connexion au flux…
                </li>
                <li v-for="(line, i) in logs" :key="i" class="break-words text-muted">
                  {{ line }}
                </li>
              </ul>
            </div>
          </UCard>
        </div>

        <UAccordion
          v-if="lastSummary && typeof lastSummary === 'object'"
          type="single"
          class="shrink-0 border border-default rounded-lg"
          :items="summaryAccordionItems"
          default-value="json"
          :ui="{ item: 'border-0' }"
        >
          <template #content>
            <pre
              class="max-h-64 overflow-auto rounded-md bg-elevated/50 p-3 text-xs ring ring-default"
            >{{ JSON.stringify(lastSummary, null, 2) }}</pre>
          </template>
        </UAccordion>
      </div>
    </template>
  </UDashboardPanel>
</template>
