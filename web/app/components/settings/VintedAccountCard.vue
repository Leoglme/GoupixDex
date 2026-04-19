<script setup lang="ts">
const { me, refreshMe } = useAuth()
const { updateMyVintedCredentials } = useUsers()
const toast = useToast()

const email = ref('')
const password = ref('')
const saving = ref(false)

const linked = computed(() => Boolean(me.value?.vinted_email))

watch(
  () => me.value?.vinted_email,
  (val) => {
    email.value = val ?? ''
  },
  { immediate: true }
)

async function save() {
  saving.value = true
  try {
    const trimmedEmail = email.value.trim()
    await updateMyVintedCredentials({
      vinted_email: trimmedEmail || null,
      // Empty password = keep existing one (don't overwrite)
      ...(password.value ? { vinted_password: password.value } : {})
    })
    password.value = ''
    await refreshMe()
    toast.add({ title: 'Compte Vinted enregistré', color: 'success' })
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  } finally {
    saving.value = false
  }
}

async function unlink() {
  if (!confirm('Détacher votre compte Vinted ? Les publications Vinted seront désactivées.')) {
    return
  }
  saving.value = true
  try {
    await updateMyVintedCredentials({
      vinted_email: null,
      vinted_password: ''
    })
    email.value = ''
    password.value = ''
    await refreshMe()
    toast.add({ title: 'Compte Vinted détaché', color: 'success' })
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <UCard>
    <template #header>
      <div class="space-y-1">
        <div class="flex items-center justify-between gap-3">
          <p class="font-medium text-highlighted">
            Compte Vinted
          </p>
          <UBadge :color="linked ? 'success' : 'neutral'" variant="subtle">
            {{ linked ? 'Lié' : 'Non lié' }}
          </UBadge>
        </div>
        <p class="text-sm text-muted">
          GoupixDex publie vos annonces depuis votre propre compte Vinted. Renseignez votre e-mail
          et mot de passe Vinted ; ils sont chiffrés en base.
        </p>
      </div>
    </template>

    <form class="space-y-4" @submit.prevent="save">
      <UFormField label="E-mail Vinted">
        <UInput
          v-model="email"
          type="email"
          autocomplete="email"
          placeholder="vous@exemple.com"
          class="w-full"
        />
      </UFormField>

      <UFormField
        :label="linked ? 'Mot de passe Vinted (laisser vide pour conserver l\'actuel)' : 'Mot de passe Vinted'"
      >
        <PasswordInput
          v-model="password"
          autocomplete="new-password"
          :required="!linked"
        />
      </UFormField>

      <div class="flex flex-wrap items-center gap-2">
        <UButton type="submit" color="primary" :loading="saving" icon="i-lucide-save">
          {{ linked ? 'Mettre à jour' : 'Enregistrer' }}
        </UButton>
        <UButton
          v-if="linked"
          type="button"
          variant="ghost"
          color="error"
          icon="i-lucide-unlink"
          :disabled="saving"
          @click="unlink"
        >
          Détacher le compte
        </UButton>
      </div>
    </form>
  </UCard>
</template>
