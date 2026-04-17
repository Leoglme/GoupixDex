<script setup lang="ts">
definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Paramètres — configuration',
  'Réglages GoupixDex : marge appliquée aux prix et préférences liées à votre compte marchand.'
)

const { getSettings, updateSettings } = useSettings()
const toast = useToast()

const margin = ref(20)
const loading = ref(true)
const saving = ref(false)

async function load() {
  loading.value = true
  try {
    const s = await getSettings()
    margin.value = s.margin_percent ?? 20
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
})

async function saveMargin() {
  saving.value = true
  try {
    const s = await updateSettings({ margin_percent: margin.value })
    margin.value = s.margin_percent
    toast.add({ title: 'Marge enregistrée', color: 'success' })
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  } finally {
    saving.value = false
  }
}

</script>

<template>
  <div
    class="grid w-full grid-cols-1 gap-4 sm:gap-6 md:grid-cols-2 xl:grid-cols-3 items-start"
  >
    <UCard class="min-w-0">
      <template #header>
        <p class="font-medium text-highlighted">
          Marge de revente (%)
        </p>
        <p class="text-sm text-muted">
          Utilisée pour le prix suggéré (PokéWallet + marge) lors du scan et du lookup.
        </p>
      </template>
      <div v-if="loading" class="text-muted text-sm">
        Chargement…
      </div>
      <div v-else class="space-y-4">
        <UFormField label="Pourcentage">
          <UInput
            v-model.number="margin"
            type="number"
            min="0"
            max="500"
            class="w-full max-w-xs"
          />
        </UFormField>
        <UButton :loading="saving" @click="saveMargin">
          Enregistrer
        </UButton>
      </div>
    </UCard>
  </div>
</template>
