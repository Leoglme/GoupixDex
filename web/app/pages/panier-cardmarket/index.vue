<template>
  <UDashboardPanel id="panier-cardmarket">
    <template #header>
      <UDashboardNavbar title="Panier Cardmarket">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton color="primary" icon="i-lucide-plus" @click="openCreate = true"> Nouveau panier </UButton>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="space-y-6 px-4 py-6 sm:px-6 sm:py-8">
        <div
          class="border-default from-primary/10 via-elevated/60 to-primary/5 relative overflow-hidden rounded-2xl border bg-gradient-to-br px-5 py-5 sm:px-7 sm:py-7"
        >
          <div class="bg-primary/10 pointer-events-none absolute -top-16 -right-16 size-48 rounded-full blur-3xl" />
          <div class="bg-primary/5 pointer-events-none absolute -bottom-24 -left-10 size-44 rounded-full blur-3xl" />
          <div class="relative max-w-3xl space-y-2">
            <p class="text-primary text-xs font-medium tracking-wide uppercase">Cardmarket · Achat groupé</p>
            <h1 class="text-highlighted text-xl font-semibold tracking-tight sm:text-2xl">
              Trouvez les vendeurs qui couvrent le plus de cartes
            </h1>
            <p class="text-muted text-sm leading-relaxed sm:text-base">
              Collez les liens produit Cardmarket (singles), lancez l’analyse depuis l’app bureau : GoupixDex agrège les
              offres, classe les vendeurs par nombre de cartes et par surcoût par rapport au meilleur prix connu.
            </p>
          </div>
        </div>

        <UAlert
          v-if="!isDesktopApp"
          color="warning"
          variant="subtle"
          icon="i-lucide-monitor-down"
          title="Application bureau requise"
          description="L’analyse utilise Chrome sur votre machine (nodriver). Ouvrez GoupixDex en version desktop pour lancer une recherche."
        />

        <GoupixDexCardmarketSessionBanner v-if="isDesktopApp" :session="cmSession" :loading="cmSessionLoading" />

        <UAlert
          v-if="error"
          color="error"
          variant="subtle"
          icon="i-lucide-alert-triangle"
          title="Erreur"
          :description="error"
        />

        <UTable
          :data="rows"
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
      </div>
    </template>
  </UDashboardPanel>

  <UModal v-model:open="openCreate" title="Nouveau panier">
    <template #body>
      <div class="space-y-4 p-4 sm:p-6">
        <UFormField label="Nom (optionnel)">
          <UInput v-model="createName" placeholder="Laisser vide pour un nom automatique" />
        </UFormField>
        <UFormField
          label="Liens Cardmarket"
          :hint="createDetectedHint"
          help="Collez vos liens en bloc (un par ligne, ou séparés par espaces / virgules) — GoupixDex extrait et déduplique automatiquement."
          required
        >
          <UTextarea
            v-model="createUrlsText"
            :rows="10"
            autoresize
            class="w-full font-mono text-xs"
            placeholder="https://www.cardmarket.com/fr/Pokemon/Products/Singles/...&#10;https://www.cardmarket.com/fr/Pokemon/Products/Singles/..."
          />
        </UFormField>
      </div>
    </template>
    <template #footer>
      <div class="flex justify-end gap-2 p-4 sm:px-6">
        <UButton color="neutral" variant="ghost" @click="openCreate = false"> Annuler </UButton>
        <UButton color="primary" :loading="creating" :disabled="!createDetectedUrls.length" @click="onCreate">
          Créer
        </UButton>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import type { Ref } from 'vue'
import type { TableColumn } from '@nuxt/ui'
import type { Row } from '@tanstack/table-core'
import type { CardmarketSearchListRow } from '~/types/CardmarketSearch'
import type { CardmarketSessionResponse } from '~/types/CardmarketSession'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Panier Cardmarket',
  'Enregistrez des listes de liens Cardmarket et identifiez les vendeurs les plus rentables pour limiter les frais de port.',
)

const toast = useToast()
const { listSearches, createSearch, deleteSearch, isDesktopApp } = useCardmarketSearches()
const { fetchSession: fetchCmSession } = useCardmarketWorker()

const rows: Ref<CardmarketSearchListRow[]> = ref([])
const loading: Ref<boolean> = ref(true)
const error: Ref<string | null> = ref(null)
const openCreate: Ref<boolean> = ref(false)
const createName: Ref<string> = ref('')
const createUrlsText: Ref<string> = ref('')
const creating: Ref<boolean> = ref(false)
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

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    rows.value = await listSearches()
  } catch (e: unknown) {
    error.value = apiErrorMessage(e)
  } finally {
    loading.value = false
  }
}

const createDetectedUrls = computed(() => parseCardmarketUrlsFromText(createUrlsText.value))

const createDetectedHint = computed(() => {
  const n = createDetectedUrls.value.length
  if (!n) {
    return 'Aucun lien détecté'
  }
  return `${n} lien${n > 1 ? 's' : ''} détecté${n > 1 ? 's' : ''}`
})

async function onCreate(): Promise<void> {
  const urls = createDetectedUrls.value
  if (!urls.length) {
    toast.add({ title: 'Au moins un lien Cardmarket requis', color: 'warning' })
    return
  }
  creating.value = true
  try {
    const name = createName.value.trim() || null
    const created = await createSearch({ name, urls })
    openCreate.value = false
    createName.value = ''
    createUrlsText.value = ''
    toast.add({
      title: 'Panier créé',
      description: `${urls.length} lien${urls.length > 1 ? 's' : ''} ajouté${urls.length > 1 ? 's' : ''}.`,
      color: 'success',
    })
    await load()
    await navigateTo(`/panier-cardmarket/${created.id}`)
  } catch (e: unknown) {
    toast.add({ title: 'Création impossible', description: apiErrorMessage(e), color: 'error' })
  } finally {
    creating.value = false
  }
}

function goRow(row: Row<CardmarketSearchListRow>): void {
  void navigateTo(`/panier-cardmarket/${row.original.id}`)
}

async function removeRow(row: Row<CardmarketSearchListRow>): Promise<void> {
  const ok = window.confirm(`Supprimer le panier « ${row.original.name || `#${row.original.id}`} » ?`)
  if (!ok) {
    return
  }
  try {
    await deleteSearch(row.original.id)
    toast.add({ title: 'Panier supprimé', color: 'success' })
    await load()
  } catch (e: unknown) {
    toast.add({ title: 'Suppression impossible', description: apiErrorMessage(e), color: 'error' })
  }
}

const columns: TableColumn<CardmarketSearchListRow>[] = [
  {
    accessorKey: 'name',
    header: 'Nom',
    cell: ({ row }) =>
      h(
        'button',
        {
          type: 'button',
          class:
            'text-primary hover:text-primary/80 text-left font-medium underline-offset-2 hover:underline truncate max-w-[14rem]',
          onClick: (): void => goRow(row),
        },
        row.original.name || `Panier #${row.original.id}`,
      ),
  },
  {
    accessorKey: 'url_count',
    header: 'Liens',
    cell: ({ row }) => h('span', { class: 'tabular-nums' }, String(row.original.url_count)),
  },
  {
    accessorKey: 'max_seller_coverage',
    header: 'Couv. max',
    cell: ({ row }) =>
      h(
        'span',
        { class: 'tabular-nums text-muted' },
        row.original.max_seller_coverage != null ? String(row.original.max_seller_coverage) : '—',
      ),
  },
  {
    accessorKey: 'last_ran_at',
    header: 'Dernier run',
    cell: ({ row }) => {
      const iso = row.original.last_ran_at
      if (!iso) {
        return h('span', { class: 'text-muted text-sm' }, '—')
      }
      try {
        return h('span', { class: 'text-sm tabular-nums' }, new Date(iso).toLocaleString('fr-FR'))
      } catch {
        return h('span', { class: 'text-muted text-sm' }, '—')
      }
    },
  },
  {
    id: 'actions',
    cell: ({ row }) =>
      h('div', { class: 'flex justify-end gap-1' }, [
        h(resolveComponent('UButton'), {
          size: 'xs',
          color: 'neutral',
          variant: 'ghost',
          icon: 'i-lucide-chevron-right',
          onClick: (): void => goRow(row),
        }),
        h(resolveComponent('UButton'), {
          size: 'xs',
          color: 'error',
          variant: 'ghost',
          icon: 'i-lucide-trash-2',
          onClick: (): void => {
            void removeRow(row)
          },
        }),
      ]),
  },
]

onMounted((): void => {
  void load()
  void loadCardmarketSession()
})

watch(isDesktopApp, (desktop) => {
  if (desktop) {
    void loadCardmarketSession()
  } else {
    cmSession.value = null
  }
})
</script>
