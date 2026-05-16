<template>
  <UDashboardPanel id="orders">
    <template #header>
      <UDashboardNavbar title="Commandes Cardmarket">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <div class="flex flex-wrap items-center gap-2">
            <input
              ref="pdfInputRef"
              type="file"
              accept="application/pdf"
              multiple
              class="hidden"
              @change="onPdfSelected"
            />
            <UButton
              v-if="isDesktopApp"
              color="primary"
              variant="soft"
              icon="i-lucide-cloud-download"
              :loading="syncRunning"
              :disabled="syncRunning"
              @click="onSync"
            >
              Synchroniser Cardmarket
            </UButton>
            <UButton
              v-if="isDesktopApp && syncRunning"
              color="error"
              variant="soft"
              icon="i-lucide-square"
              :loading="syncCancelling"
              @click="onCancelSync"
            >
              Arrêter
            </UButton>
            <UButton color="primary" icon="i-lucide-file-up" :loading="importing" @click="openPdfPicker">
              Importer des PDF
            </UButton>
            <UButton color="neutral" variant="ghost" icon="i-lucide-refresh-cw" :loading="loading" @click="load" />
          </div>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="space-y-4 p-4 sm:p-6">
        <GoupixDexCardmarketSessionBanner v-if="isDesktopApp" :session="cmSession" :loading="cmSessionLoading" />

        <UAlert
          v-if="cloudflareWaiting"
          color="warning"
          variant="subtle"
          icon="i-lucide-shield-alert"
          title="Vérification Cloudflare requise"
          :description="cloudflareMessage"
        />

        <UCard v-if="syncRunning || syncLogLines.length" class="ring-default/60 shadow-sm ring-1">
          <template #header>
            <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div class="flex items-center gap-2">
                <p class="text-highlighted font-medium">Synchronisation Cardmarket</p>
                <UBadge v-if="cloudflareWaiting" color="warning" variant="subtle" size="sm">
                  En attente Cloudflare
                </UBadge>
                <UBadge v-else-if="syncRunning" color="primary" variant="subtle" size="sm">En cours…</UBadge>
                <UBadge v-else color="neutral" variant="subtle" size="sm">Terminé</UBadge>
              </div>
              <div class="text-muted text-xs tabular-nums">
                <span v-if="syncTotals.imported || syncTotals.skipped || syncTotals.failed">
                  {{ syncTotals.imported }} importée(s) · {{ syncTotals.skipped }} ignorée(s) ·
                  {{ syncTotals.failed }} échec(s)
                </span>
                <span v-else>Préparation…</span>
              </div>
            </div>
          </template>
          <div class="space-y-3 p-4 sm:p-6">
            <UProgress v-if="syncRunning && syncTotalDiscovered > 0" :model-value="syncProgressPercent" size="sm" />
            <pre
              ref="syncLogEl"
              class="border-default bg-elevated/40 max-h-64 overflow-auto rounded-lg border p-3 font-mono text-xs whitespace-pre-wrap"
              >{{ syncLogLines.join('\n') }}</pre
            >
          </div>
        </UCard>

        <UInput
          v-model="search"
          class="w-full max-w-xl"
          icon="i-lucide-search"
          placeholder="Set + n° carte (ex. m1l 074), n° commande, vendeur…"
          :loading="loading"
        />

        <UTable
          ref="tableRef"
          v-model:pagination="pagination"
          :pagination-options="{ getPaginationRowModel: getPaginationRowModel() }"
          :data="orders"
          :columns="columns"
          :loading="loading"
          class="shrink-0"
          :ui="{
            base: 'table-fixed border-separate border-spacing-0',
            thead: '[&>tr]:bg-elevated/50 [&>tr]:after:content-none',
            tbody: '[&>tr]:last:[&>td]:border-b-0',
            th: 'py-2 first:rounded-l-lg last:rounded-r-lg border-y border-default first:border-l last:border-r',
            td: 'border-b border-default',
            separator: 'h-0',
          }"
        />

        <div class="border-default flex items-center justify-between gap-3 border-t pt-4">
          <div class="text-muted text-sm">{{ orders.length }} commande(s).</div>
          <UPagination
            :default-page="(tableRef?.tableApi?.getState().pagination.pageIndex || 0) + 1"
            :items-per-page="tableRef?.tableApi?.getState().pagination.pageSize"
            :total="orders.length"
            @update:page="(p: number) => tableRef?.tableApi?.setPageIndex(p - 1)"
          />
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { Ref } from 'vue'
import type { TableColumn } from '@nuxt/ui'
import type { Row } from '@tanstack/table-core'
import { getPaginationRowModel } from '@tanstack/table-core'
import type { OrderListRow, OrdersSyncEvent } from '~/types/Orders'
import type { CardmarketSessionResponse } from '~/types/CardmarketSession'
import { cardmarketSellerProfileUrl } from '~/utils/cardmarket'
import { countryFlagImgUrl } from '~/utils/flagEmoji'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Commandes Cardmarket',
  'Importez vos factures Cardmarket et associez chaque achat à vos articles GoupixDex.',
)

const UButton = resolveComponent('UButton')
const toast = useToast()
const tableRef = useTemplateRef('tableRef')
const pdfInputRef = useTemplateRef<HTMLInputElement>('pdfInputRef')
const syncLogEl = useTemplateRef<HTMLElement>('syncLogEl')

const { listOrders, importOrderPdf } = useOrders()
const { isDesktopApp, getActiveSync, cancelSync, openProgressSocket, runWithProgress } = useCardmarketOrdersSync()
const { fetchSession: fetchCmSession } = useCardmarketWorker()

const orders: Ref<OrderListRow[]> = ref([])
const loading: Ref<boolean> = ref(true)
const importing: Ref<boolean> = ref(false)
const search: Ref<string> = ref('')
const pagination: Ref<{ pageIndex: number; pageSize: number }> = ref({
  pageIndex: 0,
  pageSize: 10,
})

const cmSession: Ref<CardmarketSessionResponse | null> = ref(null)
const cmSessionLoading: Ref<boolean> = ref(false)

const syncRunning: Ref<boolean> = ref(false)
const syncCancelling: Ref<boolean> = ref(false)
const syncLogLines: Ref<string[]> = ref([])
const syncTotals: Ref<{ discovered: number; imported: number; skipped: number; failed: number }> = ref({
  discovered: 0,
  imported: 0,
  skipped: 0,
  failed: 0,
})
const syncTotalDiscovered: Ref<number> = ref(0)
const cloudflareWaiting: Ref<boolean> = ref(false)
const cloudflareMessage: Ref<string> = ref('')
let syncWsCleanup: (() => void) | null = null

const syncProgressPercent = computed(() => {
  if (!syncTotalDiscovered.value) {
    return 0
  }
  const handled = syncTotals.value.imported + syncTotals.value.skipped + syncTotals.value.failed
  return Math.min(100, Math.round((handled / syncTotalDiscovered.value) * 100))
})

const eur: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
})

function formatWhen(iso: string | null): string {
  if (!iso) {
    return '—'
  }
  try {
    return new Date(iso).toLocaleDateString('fr-FR')
  } catch {
    return '—'
  }
}

/**
 * Load orders from the API for the table.
 * @returns {Promise<void>} Nothing.
 */
async function load(): Promise<void> {
  loading.value = true
  try {
    const q = search.value.trim()
    orders.value = await listOrders(q ? { search: q } : {})
    pagination.value = { ...pagination.value, pageIndex: 0 }
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  } finally {
    loading.value = false
  }
}

/**
 * Open the hidden PDF file picker.
 * @returns {void} Nothing.
 */
function openPdfPicker(): void {
  pdfInputRef.value?.click()
}

/**
 * Import one or more Cardmarket PDFs; refresh list; open detail only when a single file succeeds.
 * @param e - Native change event from the file input.
 * @returns {Promise<void>} Nothing.
 */
async function onPdfSelected(e: Event): Promise<void> {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  input.value = ''
  if (!files.length) {
    return
  }
  importing.value = true
  let ok = 0
  let fail = 0
  const errorSamples: string[] = []
  let lastImportedId: number | null = null
  try {
    for (const file of files) {
      try {
        const order = await importOrderPdf(file)
        ok += 1
        lastImportedId = order.id
      } catch (err) {
        fail += 1
        if (errorSamples.length < 5) {
          errorSamples.push(`${file.name}: ${apiErrorMessage(err)}`)
        }
      }
    }
    await load()
    if (ok > 0 && fail === 0) {
      toast.add({
        title: ok === 1 ? 'Commande importée' : `${ok} commandes importées`,
        description: ok === 1 ? undefined : 'Liste mise à jour.',
        color: 'success',
      })
      if (ok === 1 && lastImportedId != null) {
        await navigateTo(`/orders/${lastImportedId}`)
      }
    } else if (ok > 0 && fail > 0) {
      toast.add({
        title: `${ok} importée(s), ${fail} échec(s)`,
        description: errorSamples.join(' · '),
        color: 'warning',
      })
    } else {
      toast.add({
        title: 'Import impossible',
        description: errorSamples[0] ?? 'Erreur inconnue',
        color: 'error',
      })
    }
  } finally {
    importing.value = false
  }
}

/**
 * Navigate to the order detail route when a row is activated.
 * @param row - Table row wrapper.
 * @returns {void} Nothing.
 */
function goOrder(row: Row<OrderListRow>): void {
  void navigateTo(`/orders/${row.original.id}`)
}

const columns: TableColumn<OrderListRow>[] = [
  {
    accessorKey: 'external_order_id',
    header: 'N° commande',
    cell: ({ row }) =>
      h(
        'button',
        {
          type: 'button',
          class:
            'text-primary hover:text-primary/80 font-medium tabular-nums underline-offset-2 hover:underline text-left',
          onClick: (): void => goOrder(row),
        },
        `#${row.original.external_order_id}`,
      ),
  },
  {
    accessorKey: 'seller_username',
    header: 'Vendeur',
    cell: ({ row }) => {
      const o = row.original
      const href = cardmarketSellerProfileUrl(o.seller_username)
      const name = o.seller_username || '—'
      const title = href
        ? h(
            'a',
            {
              href,
              target: '_blank',
              rel: 'noopener noreferrer',
              class:
                'font-medium text-primary truncate underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary',
            },
            name,
          )
        : h('p', { class: 'font-medium text-highlighted truncate' }, name)
      return h('div', { class: 'min-w-0' }, [
        title,
        o.seller_display_name ? h('p', { class: 'text-muted truncate text-xs' }, o.seller_display_name) : null,
      ])
    },
  },
  {
    accessorKey: 'seller_country_code',
    header: 'Pays',
    cell: ({ row }) => {
      const cc = row.original.seller_country_code
      const src = countryFlagImgUrl(cc)
      if (!src) {
        return h('span', { class: 'text-muted text-xs' }, '—')
      }
      return h('span', { class: 'inline-flex items-center gap-2' }, [
        h('img', {
          src,
          alt: '',
          class: 'inline-block h-[23px] w-[30px] shrink-0 rounded-sm object-cover',
          width: 30,
          height: 23,
          loading: 'lazy',
          decoding: 'async',
        }),
        h('span', { class: 'sr-only' }, cc ?? ''),
      ])
    },
  },
  {
    accessorKey: 'paid_at',
    header: 'Payé le',
    cell: ({ row }) => h('span', { class: 'text-sm tabular-nums' }, formatWhen(row.original.paid_at)),
  },
  {
    accessorKey: 'shipped_at',
    header: 'Envoyé le',
    cell: ({ row }) => h('span', { class: 'text-sm tabular-nums' }, formatWhen(row.original.shipped_at)),
  },
  {
    accessorKey: 'delivered_at',
    header: 'Livré le',
    cell: ({ row }) => h('span', { class: 'text-sm tabular-nums' }, formatWhen(row.original.delivered_at)),
  },
  {
    accessorKey: 'item_units',
    header: 'Articles',
    cell: ({ row }) => h('span', { class: 'tabular-nums' }, String(row.original.item_units ?? row.original.line_count)),
  },
  {
    accessorKey: 'items_subtotal',
    header: 'Sous-total',
    cell: ({ row }) => h('span', { class: 'tabular-nums' }, eur.format(row.original.items_subtotal)),
  },
  {
    accessorKey: 'shipping_fee',
    header: 'Port',
    cell: ({ row }) => h('span', { class: 'tabular-nums' }, eur.format(row.original.shipping_fee)),
  },
  {
    accessorKey: 'order_total',
    header: 'Total',
    cell: ({ row }) => h('span', { class: 'font-medium tabular-nums' }, eur.format(row.original.order_total)),
  },
  {
    accessorKey: 'sold_articles_count',
    header: 'Vendus',
    cell: ({ row }) => {
      const o = row.original
      return h('span', { class: 'tabular-nums text-muted' }, `${o.sold_articles_count} / ${o.item_units}`)
    },
  },
  {
    id: 'open',
    cell: ({ row }) =>
      h(
        UButton,
        {
          size: 'xs',
          color: 'neutral',
          variant: 'ghost',
          icon: 'i-lucide-chevron-right',
          onClick: (): void => goOrder(row),
        },
        () => '',
      ),
  },
]

let searchDebounce: ReturnType<typeof setTimeout> | undefined

watch(search, () => {
  if (searchDebounce !== undefined) {
    clearTimeout(searchDebounce)
  }
  searchDebounce = setTimeout((): void => {
    searchDebounce = undefined
    void load()
  }, 320)
})

/**
 * Append one line to the in-page sync log and auto-scroll the panel to the bottom.
 * @param line - Text to append.
 */
function appendSyncLog(line: string): void {
  syncLogLines.value = [...syncLogLines.value, line]
  void nextTick((): void => {
    const el = syncLogEl.value
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  })
}

/**
 * Reset Cloudflare banner / log state and free the WebSocket cleanup function.
 * Called on terminal sync events (`done`, `error`, `cancelled`).
 */
function finalizeSync(): void {
  syncRunning.value = false
  syncCancelling.value = false
  cloudflareWaiting.value = false
  cloudflareMessage.value = ''
  syncWsCleanup?.()
  syncWsCleanup = null
  void loadCardmarketSession()
}

/**
 * Apply one streamed sync event to the local UI state.
 * @param ev - Event broadcast by the desktop worker.
 */
function applySyncEvent(ev: OrdersSyncEvent): void {
  if (ev.totals) {
    syncTotals.value = {
      discovered: Number(ev.totals.discovered ?? syncTotals.value.discovered) || syncTotals.value.discovered,
      imported: Number(ev.totals.imported ?? syncTotals.value.imported) || syncTotals.value.imported,
      skipped: Number(ev.totals.skipped ?? syncTotals.value.skipped) || syncTotals.value.skipped,
      failed: Number(ev.totals.failed ?? syncTotals.value.failed) || syncTotals.value.failed,
    }
  }

  if (ev.type === 'session_status') {
    void loadCardmarketSession()
    if (ev.logged_in === false && ev.message) {
      appendSyncLog(`⚠ ${ev.message}`)
    }
    return
  }
  if (ev.type === 'log' && ev.message) {
    appendSyncLog(ev.message)
    return
  }
  if (ev.type === 'page') {
    if (typeof ev.rows_on_page === 'number') {
      syncTotalDiscovered.value += ev.rows_on_page
    }
    appendSyncLog(
      `Page ${ev.page ?? '?'}${ev.total_pages ? ` / ${ev.total_pages}` : ''} — ${ev.rows_on_page ?? 0} commande(s).`,
    )
    return
  }
  if (ev.type === 'order_start') {
    appendSyncLog(`→ Commande #${ev.external_order_id ?? ''} (${ev.seller ?? ''}) ${ev.total_text ?? ''}`)
    return
  }
  if (ev.type === 'order_imported') {
    appendSyncLog(`✓ Importée #${ev.external_order_id ?? ''}`)
    return
  }
  if (ev.type === 'skip') {
    appendSyncLog(`• Ignorée #${ev.external_order_id ?? ''}${ev.message ? ` — ${ev.message}` : ''}`)
    return
  }
  if (ev.type === 'order_failed') {
    appendSyncLog(`✗ Échec #${ev.external_order_id ?? ''} — ${ev.message ?? 'erreur inconnue'}`)
    return
  }
  if (ev.type === 'cloudflare_wait') {
    cloudflareWaiting.value = true
    cloudflareMessage.value =
      ev.message ?? 'Cloudflare demande une vérification — cochez la case dans la fenêtre Chrome ouverte par GoupixDex.'
    appendSyncLog('⚠ Cloudflare — vérification manuelle requise')
    return
  }
  if (ev.type === 'cloudflare_resolved') {
    cloudflareWaiting.value = false
    cloudflareMessage.value = ''
    appendSyncLog('✓ Cloudflare résolu, reprise…')
    return
  }
  if (ev.type === 'cloudflare_timeout') {
    cloudflareWaiting.value = false
    appendSyncLog('✗ Cloudflare non résolu dans les temps.')
    return
  }
  if (ev.type === 'error') {
    appendSyncLog(`ERREUR : ${ev.message ?? ''}`)
    finalizeSync()
    toast.add({ title: 'Synchronisation interrompue', description: ev.message ?? '', color: 'error' })
    void load()
    return
  }
  if (ev.type === 'cancelled') {
    appendSyncLog('■ Synchronisation arrêtée.')
    finalizeSync()
    toast.add({ title: 'Synchronisation arrêtée', color: 'warning' })
    void load()
    return
  }
  if (ev.type === 'done') {
    const s = ev.summary ?? syncTotals.value
    appendSyncLog(`Terminé. ${s.imported ?? 0} importée(s), ${s.skipped ?? 0} ignorée(s), ${s.failed ?? 0} échec(s).`)
    finalizeSync()
    toast.add({
      title: 'Synchronisation terminée',
      description: `${s.imported ?? 0} nouvelle(s) commande(s) importée(s).`,
      color: 'success',
    })
    void load()
  }
}

/**
 * Reset progress state before starting (or attaching to) a sync run.
 */
function resetSyncState(): void {
  syncLogLines.value = []
  syncTotals.value = { discovered: 0, imported: 0, skipped: 0, failed: 0 }
  syncTotalDiscovered.value = 0
  cloudflareWaiting.value = false
  cloudflareMessage.value = ''
}

/**
 * Trigger the desktop worker sync and stream progress live.
 */
async function onSync(): Promise<void> {
  if (!isDesktopApp.value || syncRunning.value) {
    return
  }
  resetSyncState()
  syncRunning.value = true
  try {
    const { close } = await runWithProgress(applySyncEvent)
    syncWsCleanup = close
  } catch (e) {
    syncRunning.value = false
    toast.add({ title: 'Lancement impossible', description: apiErrorMessage(e), color: 'error' })
  }
}

/**
 * Send the cancel request; the worker emits `cancelled` to clean up the UI.
 */
async function onCancelSync(): Promise<void> {
  if (!syncRunning.value || syncCancelling.value) {
    return
  }
  syncCancelling.value = true
  try {
    await cancelSync()
    appendSyncLog('Demande d’arrêt envoyée…')
  } catch (e) {
    syncCancelling.value = false
    toast.add({ title: 'Arrêt impossible', description: apiErrorMessage(e), color: 'error' })
  }
}

/**
 * Refresh the Cardmarket session banner (logged-in / needs_login state).
 */
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

/**
 * On mount, reattach to a sync that might already be running on the worker.
 */
async function reattachActiveSync(): Promise<void> {
  if (!isDesktopApp.value) {
    return
  }
  try {
    const { active, last_event } = await getActiveSync()
    if (!active) {
      return
    }
    resetSyncState()
    syncRunning.value = true
    if (last_event) {
      applySyncEvent(last_event)
    }
    const ws = await openProgressSocket(applySyncEvent)
    if (ws) {
      syncWsCleanup = (): void => {
        try {
          ws.close()
        } catch {
          /* ignore */
        }
      }
    } else {
      syncRunning.value = false
    }
  } catch {
    /* worker offline — ignore */
  }
}

onMounted((): void => {
  void load()
  void loadCardmarketSession()
  void reattachActiveSync()
})

watch(isDesktopApp, (desktop) => {
  if (desktop) {
    void loadCardmarketSession()
    void reattachActiveSync()
  } else {
    cmSession.value = null
  }
})

onBeforeUnmount((): void => {
  syncWsCleanup?.()
  syncWsCleanup = null
})
</script>
