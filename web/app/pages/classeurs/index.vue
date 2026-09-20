<template>
  <UDashboardPanel id="binders-list">
    <template #header>
      <UDashboardNavbar>
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #title>
          <span class="app-label flex items-center gap-1.5 !text-[0.65rem]">
            <UIcon name="i-lucide-bookmark" class="h-3 w-3 text-(--app-accent)" />
            Collection
          </span>
        </template>
        <template #right>
          <UButton color="neutral" variant="ghost" icon="i-lucide-refresh-cw" :loading="loading" @click="load" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="app-dashboard-page w-full space-y-4">
        <GoupixDexPageHeader
          title="Classeurs"
          description="Sous-collections thématiques : rangez des cartes de ma collection dans des pochettes."
        >
          <template #actions>
            <UButton color="primary" icon="i-lucide-plus" :loading="creating" @click="openCreate">
              Nouveau classeur
            </UButton>
          </template>
        </GoupixDexPageHeader>

        <div v-if="loading" class="flex justify-center py-16">
          <UIcon name="i-lucide-loader-2" class="size-10 animate-spin text-(--app-accent)" />
        </div>

        <UAlert
          v-else-if="loadError"
          color="error"
          icon="i-lucide-database"
          title="Classeurs indisponibles"
          :description="loadError"
        />

        <UCard v-else-if="binders.length === 0" :ui="{ body: 'p-10 text-center' }">
          <UIcon name="i-lucide-notebook-tabs" class="mx-auto mb-3 h-12 w-12 text-(--app-faint)" />
          <p class="font-display text-xl font-semibold">Aucun classeur</p>
          <p class="mx-auto mt-2 max-w-md text-sm text-(--app-ink-soft)">
            Un classeur par thème (set, holos…). Range tes cartes en pochettes, page par page.
          </p>
          <UButton class="mt-4" color="primary" @click="openCreate">Créer un classeur</UButton>
        </UCard>

        <GoupixDexBindersGrid v-else :binders="binders" @reordered="load" />
      </div>
    </template>
  </UDashboardPanel>

  <GoupixDexDialogModal
    v-model:open="createOpen"
    title="Nouveau classeur"
    description="Un nom clair pour retrouver ce classeur plus tard (set, holos, gradées…)."
  >
    <label class="text-muted mb-1.5 block text-xs font-medium" for="binder-create-name">Nom</label>
    <input
      id="binder-create-name"
      v-model="createName"
      type="text"
      class="app-input"
      placeholder="Ex. Holos Scarlet & Violet"
      autocomplete="off"
      @keyup.enter="submitCreate"
    />

    <template #footer>
      <button type="button" class="dialog-btn-secondary" @click="createOpen = false">Annuler</button>
      <button type="button" class="dialog-btn-primary" :disabled="creating || !createName.trim()" @click="submitCreate">
        <UIcon v-if="creating" name="i-lucide-loader-2" class="size-4 animate-spin" />
        Créer
      </button>
    </template>
  </GoupixDexDialogModal>
</template>

<script setup lang="ts">
import type { BinderSummary } from '~/types/binders'

definePageMeta({ middleware: 'auth' })

const { listBinders, createBinder } = useBinders()
const toast = useToast()
const router = useRouter()

const loading = ref(true)
const loadError = ref<string | null>(null)
const binders = ref<BinderSummary[]>([])
const createOpen = ref(false)
const createName = ref('')
const creating = ref(false)

async function load() {
  loading.value = true
  loadError.value = null
  try {
    binders.value = await listBinders()
  } catch (e) {
    loadError.value = apiErrorMessage(e)
    binders.value = []
    toast.add({ title: 'Impossible de charger les classeurs', description: loadError.value, color: 'error' })
  } finally {
    loading.value = false
  }
}

function openCreate() {
  createName.value = ''
  createOpen.value = true
}

async function submitCreate() {
  const name = createName.value.trim()
  if (!name) return
  creating.value = true
  try {
    const binder = await createBinder(name)
    createOpen.value = false
    await router.push(`/classeurs/${binder.id}`)
  } catch (e) {
    const description = apiErrorMessage(e)
    toast.add({ title: 'Création impossible', description, color: 'error' })
  } finally {
    creating.value = false
  }
}

onMounted(() => {
  void load()
})
</script>
