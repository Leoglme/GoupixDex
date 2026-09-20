<template>
  <GoupixDexAppDrawer
    :open="open"
    title="Mon profil"
    subtitle="Nom et adresse expéditeur"
    icon="i-lucide-user"
    @close="onCancel"
  >
    <div v-if="loading" class="text-muted text-sm">Chargement…</div>
    <form v-else id="goupix-profile-form" class="space-y-5" @submit.prevent="save">
      <div class="space-y-4">
        <UFormField label="Nom complet" name="full_name" required>
          <UInput v-model="form.full_name" autocomplete="name" placeholder="Jean Dupont" class="w-full" />
        </UFormField>

        <UFormField label="E-mail de connexion" name="email">
          <UInput :model-value="profile?.email ?? me?.email ?? ''" disabled class="w-full" />
        </UFormField>
      </div>

      <div class="space-y-3">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <p class="text-highlighted text-sm font-medium">Adresse expéditeur</p>
          <UBadge :color="profile?.sender_address_complete ? 'success' : 'warning'" variant="subtle">
            {{ profile?.sender_address_complete ? 'Prête' : 'Incomplète' }}
          </UBadge>
        </div>
        <div class="grid grid-cols-1 gap-x-4 gap-y-4 sm:grid-cols-2">
          <UFormField label="Adresse" class="min-w-0 sm:col-span-2" required>
            <GoupixDexAddressAutocompleteInput
              v-model="form.sender_line1"
              placeholder="Numéro et voie"
              :teleport-to-body="false"
              @select="onAddressSelect"
            />
          </UFormField>
          <UFormField label="Complément d'adresse" class="min-w-0 sm:col-span-2">
            <UInput v-model="form.sender_line2" autocomplete="address-line2" class="w-full" />
          </UFormField>
          <UFormField label="Code postal" class="min-w-0" required>
            <GoupixDexPostalCodeAutocompleteInput
              v-model="form.sender_postal_code"
              :teleport-to-body="false"
              @select="onPostalCodeSelect"
            />
          </UFormField>
          <UFormField label="Ville" class="min-w-0" required>
            <GoupixDexCityAutocompleteInput
              v-model="form.sender_city"
              :teleport-to-body="false"
              @select="onCitySelect"
            />
          </UFormField>
        </div>
      </div>
    </form>

    <template #footer>
      <button type="button" class="dialog-btn-secondary" :disabled="saving" @click="onCancel">Annuler</button>
      <button type="button" class="dialog-btn-primary" :disabled="loading || saving" @click="save">
        <UIcon v-if="saving" name="i-lucide-loader-circle" class="size-4 animate-spin" />
        {{ saving ? 'Enregistrement…' : 'Enregistrer' }}
      </button>
    </template>
  </GoupixDexAppDrawer>
</template>

<script setup lang="ts">
import type { AddressSuggestion } from '~/types/AddressAutocompleteInput'
import type { PostalCodeCitySuggestion } from '~/types/PostalCodeAutocompleteInput'
import type { CitySuggestion } from '~/types/CityAutocompleteInput'

import type { UserProfilePayload } from '~/types/userProfile'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const { me, refreshMe } = useAuth()
const { closeProfileDrawer } = useProfileDrawer()
const { $api } = useNuxtApp()
const toast = useToast()

const profile = ref<UserProfilePayload | null>(null)
const loading = ref(false)
const saving = ref(false)

const form = reactive({
  full_name: '',
  sender_line1: '',
  sender_line2: '',
  sender_postal_code: '',
  sender_city: '',
})

function onCancel(): void {
  closeProfileDrawer()
  emit('close')
}

function onAddressSelect(suggestion: AddressSuggestion): void {
  form.sender_postal_code = suggestion.postcode
  form.sender_city = suggestion.city
}

function onPostalCodeSelect(suggestion: PostalCodeCitySuggestion): void {
  form.sender_city = suggestion.nom
}

function onCitySelect(suggestion: CitySuggestion): void {
  const cp = suggestion.codesPostaux?.[0]
  if (cp && !form.sender_postal_code.trim()) {
    form.sender_postal_code = cp
  }
}

function applyProfile(data: UserProfilePayload): void {
  profile.value = data
  form.full_name = data.full_name ?? ''
  form.sender_line1 = data.sender_line1 ?? ''
  form.sender_line2 = data.sender_line2 ?? ''
  form.sender_postal_code = data.sender_postal_code ?? ''
  form.sender_city = data.sender_city ?? ''
}

async function loadProfile(): Promise<void> {
  loading.value = true
  try {
    const { data } = await $api.get<UserProfilePayload>('/users/me/profile')
    applyProfile(data)
  } catch (e: unknown) {
    toast.add({
      title: 'Profil inaccessible',
      description: e instanceof Error ? e.message : String(e),
      color: 'error',
    })
  } finally {
    loading.value = false
  }
}

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      void loadProfile()
    }
  },
)

async function save(): Promise<void> {
  if (
    !form.full_name.trim() ||
    !form.sender_line1.trim() ||
    !form.sender_postal_code.trim() ||
    !form.sender_city.trim()
  ) {
    toast.add({
      title: 'Champs requis',
      description: 'Nom complet, adresse, code postal et ville sont obligatoires.',
      color: 'warning',
    })
    return
  }
  saving.value = true
  try {
    const { data } = await $api.put<UserProfilePayload>('/users/me/profile', {
      full_name: form.full_name.trim() || null,
      sender_line1: form.sender_line1.trim() || null,
      sender_line2: form.sender_line2.trim() || null,
      sender_postal_code: form.sender_postal_code.trim() || null,
      sender_city: form.sender_city.trim() || null,
    })
    applyProfile(data)
    await refreshMe()
    toast.add({ title: 'Profil enregistré', color: 'success' })
    closeProfileDrawer()
    emit('close')
  } catch (e: unknown) {
    toast.add({
      title: 'Enregistrement impossible',
      description: e instanceof Error ? e.message : String(e),
      color: 'error',
    })
  } finally {
    saving.value = false
  }
}
</script>
