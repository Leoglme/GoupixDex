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
    class="flex flex-col gap-6"
    @submit.prevent="onSubmit"
  >
    <UAlert
      v-if="errorMsg"
      color="error"
      variant="subtle"
      :title="errorMsg"
      icon="i-lucide-circle-alert"
    />

    <UFormField
      label="E-mail"
      name="email"
      required
    >
      <UInput
        v-model="email"
        type="email"
        name="email"
        icon="i-lucide-mail"
        placeholder="vous@exemple.com"
        autocomplete="email"
        size="md"
        class="w-full"
      />
    </UFormField>

    <UFormField
      label="Mot de passe"
      name="password"
      required
    >
      <UInput
        v-model="password"
        type="password"
        name="password"
        icon="i-lucide-lock-keyhole"
        autocomplete="current-password"
        size="md"
        class="w-full"
      />
    </UFormField>

    <div class="pt-1">
      <UButton
        type="submit"
        block
        size="lg"
        color="primary"
        :loading="loading"
        icon="i-lucide-log-in"
      >
        Se connecter
      </UButton>
    </div>
  </form>
</template>
