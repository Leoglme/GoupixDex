<script setup lang="ts">
import logoUrl from '~/assets/images/logo-goupix-dev-256x256.png'
import type { PasswordSetupInfo } from '~/composables/useAccessRequests'

definePageMeta({ layout: 'auth' })

useGoupixPageSeo(
  'Définir mon mot de passe',
  'Définissez votre mot de passe GoupixDex via le lien sécurisé envoyé par votre administrateur.'
)

const route = useRoute()
const token = computed(() => String(route.params.token ?? ''))

const { fetchPasswordSetupInfo, completePasswordSetup } = useAccessRequests()
const toast = useToast()

const info = ref<PasswordSetupInfo | null>(null)
const loadingInfo = ref(true)
const loadError = ref<string | null>(null)

const password = ref('')
const password2 = ref('')
const submitting = ref(false)
const success = ref(false)

async function load() {
  loadingInfo.value = true
  loadError.value = null
  try {
    info.value = await fetchPasswordSetupInfo(token.value)
  } catch (e) {
    loadError.value = apiErrorMessage(e)
  } finally {
    loadingInfo.value = false
  }
}

onMounted(load)

async function onSubmit() {
  if (password.value.length < 8) {
    toast.add({ title: 'Mot de passe trop court (8 caractères min.)', color: 'error' })
    return
  }
  if (password.value !== password2.value) {
    toast.add({ title: 'Les mots de passe ne correspondent pas', color: 'error' })
    return
  }
  submitting.value = true
  try {
    await completePasswordSetup(token.value, password.value)
    success.value = true
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="flex min-h-dvh w-full items-center justify-center bg-elevated px-4 py-10">
    <div class="w-full max-w-md space-y-8">
      <div class="flex items-center gap-3">
        <span
          class="flex size-11 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-elevated/60 ring-1 ring-default/40"
        >
          <img
            :src="logoUrl"
            alt="GoupixDex"
            class="size-9 object-contain"
            width="36"
            height="36"
          >
        </span>
        <span class="text-lg font-semibold tracking-tight text-highlighted">GoupixDex</span>
      </div>

      <UCard>
        <template #header>
          <p class="text-lg font-semibold text-highlighted">
            Définir mon mot de passe
          </p>
          <p v-if="info" class="text-sm text-muted">
            Compte : <strong class="text-highlighted">{{ info.email }}</strong>
          </p>
        </template>

        <div v-if="loadingInfo" class="flex items-center gap-2 text-sm text-muted py-6">
          <UIcon name="i-lucide-loader-2" class="size-5 animate-spin" />
          Vérification du lien…
        </div>

        <div v-else-if="loadError" class="space-y-3">
          <UAlert
            color="error"
            variant="subtle"
            icon="i-lucide-circle-alert"
            title="Lien invalide ou expiré"
            :description="loadError"
          />
          <UButton to="/login" variant="ghost" color="neutral" icon="i-lucide-arrow-left">
            Retour à la connexion
          </UButton>
        </div>

        <div v-else-if="success" class="space-y-4">
          <div class="flex items-center gap-3 text-success">
            <UIcon name="i-lucide-check-circle-2" class="size-6" />
            <p class="font-medium">
              Mot de passe enregistré.
            </p>
          </div>
          <p class="text-sm text-muted">
            Vous pouvez vous connecter à GoupixDex avec votre adresse e-mail et le mot de passe que vous venez de définir.
          </p>
          <UButton to="/login" color="primary" block>
            Aller à la connexion
          </UButton>
        </div>

        <form v-else class="space-y-4" @submit.prevent="onSubmit">
          <UFormField label="Mot de passe (8 caractères min.)" required>
            <PasswordInput
              v-model="password"
              autocomplete="new-password"
              required
            />
          </UFormField>
          <UFormField label="Confirmer le mot de passe" required>
            <PasswordInput
              v-model="password2"
              autocomplete="new-password"
              required
            />
          </UFormField>
          <UButton
            type="submit"
            color="primary"
            block
            size="lg"
            :loading="submitting"
            icon="i-lucide-shield-check"
          >
            Enregistrer mon mot de passe
          </UButton>
        </form>
      </UCard>
    </div>
  </div>
</template>
