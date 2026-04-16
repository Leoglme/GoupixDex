<script setup lang="ts">
definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Paramètres — nouvel utilisateur',
  'Ajoutez un utilisateur GoupixDex avec ses identifiants de connexion et, si besoin, ses identifiants Vinted.'
)

const toast = useToast()
const { createUser } = useUsers()

const form = reactive({
  email: '',
  password: '',
  vinted_email: '',
  vinted_password: ''
})
const submitting = ref(false)

async function onSubmit() {
  if (form.password.length < 8) {
    toast.add({ title: 'Mot de passe trop court (8 caractères min.)', color: 'error' })
    return
  }

  submitting.value = true
  try {
    await createUser({
      email: form.email.trim(),
      password: form.password,
      vinted_email: form.vinted_email.trim() || null,
      vinted_password: form.vinted_password.trim() || null
    })
    toast.add({ title: 'Utilisateur créé', color: 'success' })
    await navigateTo('/settings/users')
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <UCard>
    <template #header>
      <p class="font-medium text-highlighted">
        Créer un utilisateur
      </p>
      <p class="text-sm text-muted">
        Renseignez les identifiants de connexion GoupixDex et, si nécessaire, ceux de Vinted.
      </p>
    </template>

    <form class="space-y-4" @submit.prevent="onSubmit">
      <UFormField label="E-mail">
        <UInput v-model="form.email" type="email" required class="w-full" />
      </UFormField>

      <UFormField label="Mot de passe (8 caractères min.)">
        <PasswordInput
          v-model="form.password"
          required
          autocomplete="new-password"
        />
      </UFormField>

      <UFormField label="E-mail Vinted">
        <UInput v-model="form.vinted_email" type="email" class="w-full" />
      </UFormField>

      <UFormField label="Mot de passe Vinted">
        <PasswordInput
          v-model="form.vinted_password"
          autocomplete="new-password"
        />
      </UFormField>

      <div class="flex items-center gap-3">
        <UButton type="submit" color="primary" variant="solid" :loading="submitting">
          Créer l'utilisateur
        </UButton>
        <UButton color="neutral" variant="ghost" to="/settings/users">
          Annuler
        </UButton>
      </div>
    </form>
  </UCard>
</template>
