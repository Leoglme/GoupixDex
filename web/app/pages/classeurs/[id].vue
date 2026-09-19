<template>
  <UDashboardPanel
    id="binder-detail"
    :ui="{
      body: viewMode === 'pages' && binder ? 'min-w-0 overflow-x-hidden p-0 sm:p-0' : 'min-w-0 overflow-x-hidden',
    }"
  >
    <template #header>
      <UDashboardNavbar>
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #title>
          <span class="app-label flex items-center gap-1.5 !text-[0.65rem]">
            <UIcon name="i-lucide-book-open" class="h-3 w-3 text-(--app-accent)" />
            Classeur
          </span>
        </template>
        <template #right>
          <UButton
            to="/classeurs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-chevron-left"
            class="hidden sm:inline-flex"
          >
            Classeurs
          </UButton>
          <UButton
            to="/classeurs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-chevron-left"
            square
            class="sm:hidden"
            aria-label="Retour aux classeurs"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div v-if="loading" class="flex justify-center py-20">
        <UIcon name="i-lucide-loader-2" class="size-10 animate-spin text-(--app-accent)" />
      </div>

      <div v-else-if="binder" class="flex min-h-0 min-w-0 flex-col overflow-x-hidden">
        <div
          class="border-default flex flex-col gap-3 border-b px-3 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:px-4 sm:py-4"
        >
          <div class="min-w-0">
            <h1 class="font-display truncate text-lg font-semibold tracking-tight sm:text-xl">{{ binder.name }}</h1>
            <p class="text-muted mt-0.5 text-xs tabular-nums sm:text-sm">{{ binderMetaLine }}</p>
          </div>

          <div class="flex flex-wrap items-center gap-2 sm:justify-end">
            <UTabs
              v-model="viewMode"
              :items="viewTabItems"
              size="sm"
              color="primary"
              variant="pill"
              :content="false"
              aria-label="Mode d'affichage"
              class="shrink-0"
              :ui="{ list: 'w-auto', trigger: 'px-3.5 py-1.5' }"
            />

            <UButton
              v-if="viewMode === 'pages'"
              size="sm"
              color="neutral"
              variant="ghost"
              :icon="cleanView ? 'i-lucide-eye' : 'i-lucide-eye-off'"
              square
              :aria-label="cleanView ? 'Afficher les contrôles' : 'Vue propre'"
              :title="cleanView ? 'Afficher les contrôles' : 'Vue propre'"
              @click="cleanView = !cleanView"
            />

            <UDropdownMenu :items="actionMenuItems">
              <UButton
                size="sm"
                color="neutral"
                variant="outline"
                icon="i-lucide-ellipsis"
                square
                aria-label="Actions"
              />
            </UDropdownMenu>
          </div>
        </div>

        <div v-if="viewMode === 'pages'" class="binder-stage mx-2 mb-3 sm:mx-4 sm:mb-4">
          <GoupixDexBinderPages
            :binder="binder"
            href-base="/collection/"
            :clean-view="cleanView"
            @updated="onBinderUpdated"
          />
        </div>

        <div v-else class="space-y-4 px-3 py-4 sm:px-4">
          <p v-if="gridItems.length === 0" class="text-muted py-12 text-center text-sm">
            Aucune carte dans ce classeur. Passe en mode Pages pour en ranger.
          </p>
          <div v-else class="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
            <NuxtLink
              v-for="item in gridItems"
              :key="item.id"
              :to="`/collection/${item.collection_card_id}`"
              class="block"
            >
              <div class="card-tile aspect-[63/88]">
                <GoupixDexBinderCardImage :src="item.image_url" :alt="item.card_name" />
                <span v-if="item.quantity > 1" class="tile-badge num top-1.5 right-1.5">×{{ item.quantity }}</span>
              </div>
              <p class="mt-1 truncate text-xs font-medium">{{ item.card_name }}</p>
            </NuxtLink>
          </div>
        </div>
      </div>
    </template>
  </UDashboardPanel>

  <GoupixDexDialogModal v-model:open="renameOpen" title="Renommer le classeur">
    <label class="text-muted mb-1.5 block text-xs font-medium" for="binder-rename">Nom</label>
    <input
      id="binder-rename"
      v-model="renameName"
      type="text"
      class="app-input"
      autocomplete="off"
      @keyup.enter="submitRename"
    />

    <template #footer>
      <button type="button" class="dialog-btn-secondary" @click="renameOpen = false">Annuler</button>
      <button type="button" class="dialog-btn-primary" :disabled="renaming || !renameName.trim()" @click="submitRename">
        <UIcon v-if="renaming" name="i-lucide-loader-2" class="size-4 animate-spin" />
        Enregistrer
      </button>
    </template>
  </GoupixDexDialogModal>
</template>

<script setup lang="ts">
import type { BinderDetail } from '~/types/binders'
import type { DropdownMenuItem } from '@nuxt/ui'

definePageMeta({ middleware: 'auth' })

const route = useRoute()
const router = useRouter()
const { getBinder, updateBinder, deleteBinder } = useBinders()
const { confirm } = useGoupixConfirm()
const toast = useToast()

const id = computed(() => Number(route.params.id))
const loading = ref(true)
const binder = ref<BinderDetail | null>(null)
const viewMode = computed({
  get: () => (route.query.vue === 'grille' ? 'grille' : 'pages') as 'pages' | 'grille',
  set: (v: 'pages' | 'grille') => {
    const q = { ...route.query }
    if (v === 'grille') {
      q.vue = 'grille'
    } else {
      delete q.vue
    }
    void router.replace({ query: q })
  },
})
const cleanView = ref(false)

const viewTabItems = [
  { label: 'Pages', value: 'pages' },
  { label: 'Grille', value: 'grille' },
]

const gridItems = computed(() => [...(binder.value?.items ?? [])].sort((a, b) => (a.position ?? 0) - (b.position ?? 0)))

const binderMetaLine = computed(() => {
  if (!binder.value) {
    return ''
  }
  const n = binder.value.card_count
  const grid = binder.value.page_grid.replace('x', '×')
  return `${n} carte${n > 1 ? 's' : ''} · feuille ${grid}`
})

const renameOpen = ref(false)
const renameName = ref('')
const renaming = ref(false)

const actionMenuItems = computed((): DropdownMenuItem[][] => [
  [
    {
      label: 'Renommer',
      icon: 'i-lucide-pencil',
      onSelect: () => {
        renameOpen.value = true
      },
    },
  ],
  [
    {
      label: 'Supprimer le classeur',
      icon: 'i-lucide-trash-2',
      color: 'error' as const,
      onSelect: () => {
        void confirmDelete()
      },
    },
  ],
])

async function load() {
  loading.value = true
  try {
    binder.value = await getBinder(id.value)
    renameName.value = binder.value.name
  } catch {
    toast.add({ title: 'Classeur introuvable', color: 'error' })
    await router.replace('/classeurs')
  } finally {
    loading.value = false
  }
}

function onBinderUpdated(detail: BinderDetail) {
  binder.value = detail
}

async function submitRename() {
  const name = renameName.value.trim()
  if (!name || !binder.value) return
  renaming.value = true
  try {
    binder.value = await updateBinder(binder.value.id, { name })
    renameOpen.value = false
  } catch {
    toast.add({ title: 'Renommage impossible', color: 'error' })
  } finally {
    renaming.value = false
  }
}

async function confirmDelete() {
  if (!binder.value) return
  const ok = await confirm({
    title: 'Supprimer ce classeur ?',
    description: 'Les cartes restent dans ma collection.',
    confirmLabel: 'Supprimer',
    confirmColor: 'error',
  })
  if (!ok) return
  try {
    await deleteBinder(binder.value.id)
    await router.push('/classeurs')
  } catch {
    toast.add({ title: 'Suppression impossible', color: 'error' })
  }
}

watch(
  () => route.params.id,
  () => {
    void load()
  },
)

onMounted(() => {
  void load()
})
</script>
