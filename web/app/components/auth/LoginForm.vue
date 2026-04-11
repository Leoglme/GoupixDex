<script setup lang="ts">
const email = ref('')
const password = ref('')
const loading = ref(false)
const errorMsg = ref<string | null>(null)

const { login } = useAuth()
const toast = useToast()

async function onSubmit() {
  errorMsg.value = null
  loading.value = true
  try {
    await login(email.value.trim(), password.value)
    toast.add({ title: 'Connexion réussie', color: 'success' })
    await navigateTo('/dashboard')
  } catch (e: unknown) {
    const msg = e && typeof e === 'object' && 'response' in e
      ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
      : null
    errorMsg.value = typeof msg === 'string' ? msg : 'Identifiants invalides'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <form
    class="flex flex-col gap-5"
    @submit.prevent="onSubmit"
  >
    <UAlert
      v-if="errorMsg"
      color="error"
      variant="subtle"
      :title="errorMsg"
    />

    <UFormField
      label="E-mail"
      name="email"
      required
      size="lg"
    >
      <UInput
        v-model="email"
        type="email"
        name="email"
        icon="i-lucide-mail"
        placeholder="vous@exemple.com"
        autocomplete="email"
        size="lg"
        class="w-full"
      />
    </UFormField>

    <UFormField
      label="Mot de passe"
      name="password"
      required
      size="lg"
    >
      <UInput
        v-model="password"
        type="password"
        name="password"
        icon="i-lucide-lock-keyhole"
        autocomplete="current-password"
        size="lg"
        class="w-full"
      />
    </UFormField>

    <UButton
      type="submit"
      block
      size="lg"
      :loading="loading"
    >
      Se connecter
    </UButton>
  </form>
</template>
