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
import type { OrderListRow } from '~/types/Orders'
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

const { listOrders, importOrderPdf } = useOrders()

const orders: Ref<OrderListRow[]> = ref([])
const loading: Ref<boolean> = ref(true)
const importing: Ref<boolean> = ref(false)
const search: Ref<string> = ref('')
const pagination: Ref<{ pageIndex: number; pageSize: number }> = ref({
  pageIndex: 0,
  pageSize: 10,
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

onMounted((): void => {
  void load()
})
</script>
