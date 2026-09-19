<template>
  <UDashboardPanel id="binder-detail">
    <template #header>
      <UDashboardNavbar>
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #title>
          <span class="truncate font-medium">{{ binder?.name ?? 'Classeur' }}</span>
        </template>
        <template #right>
          <UButton to="/classeurs" color="neutral" variant="ghost" icon="i-lucide-arrow-left"> Classeurs </UButton>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div v-if="loading" class="flex justify-center py-20">
        <UIcon name="i-lucide-loader-2" class="size-10 animate-spin text-(--app-accent)" />
      </div>

      <div v-else-if="binder" class="w-full space-y-4 px-2 py-2.5 sm:px-4 sm:py-4">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <GoupixDexPageHeader
            :title="binder.name"
            :description="`${binder.card_count} carte(s) · grille ${binder.page_grid}`"
            class="min-w-0 flex-1"
          />
          <div class="flex flex-wrap items-center gap-2">
            <UTabs v-model="viewMode" :items="viewTabs" size="sm" />
            <UButton
              v-if="viewMode === 'pages'"
              color="neutral"
              variant="soft"
              size="sm"
              :icon="cleanView ? 'i-lucide-eye' : 'i-lucide-eye-off'"
              @click="cleanView = !cleanView"
            >
              Vue propre
            </UButton>
            <UButton color="neutral" variant="soft" size="sm" icon="i-lucide-pencil" @click="renameOpen = true">
              Renommer
            </UButton>
            <UButton color="error" variant="soft" size="sm" icon="i-lucide-trash-2" @click="confirmDelete">
              Supprimer
            </UButton>
          </div>
        </div>

        <GoupixDexBinderPages
          v-if="viewMode === 'pages'"
          :binder="binder"
          href-base="/collection/"
          :clean-view="cleanView"
          @updated="onBinderUpdated"
        />

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

const viewTabs = [
  { label: 'Pages', value: 'pages' },
  { label: 'Grille', value: 'grille' },
]

const gridItems = computed(() => [...(binder.value?.items ?? [])].sort((a, b) => (a.position ?? 0) - (b.position ?? 0)))

const renameOpen = ref(false)
const renameName = ref('')
const renaming = ref(false)

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
