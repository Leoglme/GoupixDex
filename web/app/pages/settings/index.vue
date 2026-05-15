<template>
  <div class="flex w-full max-w-3xl flex-col gap-6">
    <UCard class="min-w-0">
      <template #header>
        <p class="text-highlighted font-medium">Marge de revente (%)</p>
        <p class="text-muted text-sm">Utilisée pour le prix suggéré (PokéWallet + marge) lors du scan et du lookup.</p>
      </template>
      <div v-if="loading" class="text-muted text-sm">Chargement…</div>
      <UFormField v-else label="Pourcentage">
        <UInput v-model.number="margin" type="number" min="0" max="500" class="w-full max-w-xs" />
      </UFormField>
      <template v-if="!loading" #footer>
        <div class="border-default flex justify-end border-t pt-4">
          <UButton :loading="savingMargin" @click="saveMargin"> Enregistrer </UButton>
        </div>
      </template>
    </UCard>

    <UCard class="min-w-0">
      <template #header>
        <div class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
          <div class="min-w-0 space-y-1">
            <p class="text-highlighted font-medium">Adresse expéditeur</p>
            <p class="text-muted text-sm">
              Imprimée sur la vignette <strong>L7173 placée sous</strong> chaque destinataire ; cadre resserré en
              hauteur, presque toute la largeur ; nom puis adresse complète sur <strong>une seule ligne</strong> (sans
              logo).
            </p>
          </div>
          <UBadge
            v-if="!loading"
            class="shrink-0 self-start"
            :color="senderComplete ? 'success' : 'warning'"
            variant="subtle"
          >
            {{ senderComplete ? 'Prête' : 'Incomplète' }}
          </UBadge>
        </div>
      </template>
      <div v-if="loading" class="text-muted text-sm">Chargement…</div>
      <div v-else class="grid grid-cols-1 gap-x-4 gap-y-5 sm:grid-cols-2">
        <UFormField label="Nom complet" class="min-w-0" required>
          <UInput v-model="sender.full_name" autocomplete="name" class="w-full" />
        </UFormField>
        <UFormField label="Adresse" class="min-w-0" required>
          <UInput v-model="sender.line1" autocomplete="address-line1" class="w-full" />
        </UFormField>
        <UFormField label="Complément d'adresse" class="min-w-0 sm:col-span-2">
          <UInput v-model="sender.line2" autocomplete="address-line2" class="w-full" />
        </UFormField>
        <UFormField label="Code postal" class="min-w-0" required>
          <UInput v-model="sender.postal_code" autocomplete="postal-code" class="w-full" />
        </UFormField>
        <UFormField label="Ville" class="min-w-0" required>
          <UInput v-model="sender.city" autocomplete="address-level2" class="w-full" />
        </UFormField>
      </div>
      <template v-if="!loading" #footer>
        <div class="border-default flex justify-end border-t pt-4">
          <UButton :loading="savingSender" @click="saveSender"> Enregistrer </UButton>
        </div>
      </template>
    </UCard>
  </div>
</template>

<script setup lang="ts">
import type { Ref } from 'vue'

definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Paramètres — configuration',
  "Réglages GoupixDex : marge appliquée aux prix et adresse expéditeur pour les étiquettes d'envoi.",
)

const { getSettings, updateSettings } = useSettings()
const toast = useToast()

const margin: Ref<number> = ref(20)
const sender = reactive({
  full_name: '',
  line1: '',
  line2: '',
  postal_code: '',
  city: '',
})
const senderComplete: Ref<boolean> = ref(false)
const loading: Ref<boolean> = ref(true)
const savingMargin: Ref<boolean> = ref(false)
const savingSender: Ref<boolean> = ref(false)

async function load(): Promise<void> {
  loading.value = true
  try {
    const s = await getSettings()
    margin.value = s.margin_percent ?? 20
    sender.full_name = s.sender_full_name ?? ''
    sender.line1 = s.sender_line1 ?? ''
    sender.line2 = s.sender_line2 ?? ''
    sender.postal_code = s.sender_postal_code ?? ''
    sender.city = s.sender_city ?? ''
    senderComplete.value = s.sender_address_complete === true
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  } finally {
    loading.value = false
  }
}

async function saveMargin(): Promise<void> {
  savingMargin.value = true
  try {
    const s = await updateSettings({ margin_percent: margin.value })
    margin.value = s.margin_percent
    toast.add({ title: 'Marge enregistrée', color: 'success' })
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  } finally {
    savingMargin.value = false
  }
}

async function saveSender(): Promise<void> {
  if (!sender.full_name.trim() || !sender.line1.trim() || !sender.postal_code.trim() || !sender.city.trim()) {
    toast.add({
      title: 'Champs requis',
      description: 'Nom, adresse, code postal et ville sont obligatoires.',
      color: 'warning',
    })
    return
  }
  savingSender.value = true
  try {
    const s = await updateSettings({
      sender_full_name: sender.full_name.trim(),
      sender_line1: sender.line1.trim(),
      sender_line2: sender.line2.trim() || null,
      sender_postal_code: sender.postal_code.trim(),
      sender_city: sender.city.trim(),
    })
    senderComplete.value = s.sender_address_complete === true
    toast.add({ title: 'Adresse expéditeur enregistrée', color: 'success' })
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  } finally {
    savingSender.value = false
  }
}

onMounted((): void => {
  void load()
})
</script>
