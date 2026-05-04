<template>
  <div class="bg-elevated flex min-h-dvh w-full items-center justify-center px-4 py-10">
    <div class="w-full max-w-md space-y-8">
      <div class="flex items-center gap-3">
        <span
          class="bg-elevated/60 ring-default/40 flex size-11 shrink-0 items-center justify-center overflow-hidden rounded-lg ring-1"
        >
          <img :src="logoUrl" alt="GoupixDex" class="size-9 object-contain" width="36" height="36" />
        </span>
        <span class="text-highlighted text-lg font-semibold tracking-tight">GoupixDex</span>
      </div>

      <UCard>
        <template #header>
          <p class="text-highlighted text-lg font-semibold">Définir mon mot de passe</p>
          <p v-if="info" class="text-muted text-sm">
            Compte : <strong class="text-highlighted">{{ info.email }}</strong>
          </p>
        </template>

        <div v-if="loadingInfo" class="text-muted flex items-center gap-2 py-6 text-sm">
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
          <div class="text-success flex items-center gap-3">
            <UIcon name="i-lucide-check-circle-2" class="size-6" />
            <p class="font-medium">Mot de passe enregistré.</p>
          </div>
          <p class="text-muted text-sm">
            Vous pouvez vous connecter à GoupixDex avec votre adresse e-mail et le mot de passe que vous venez de
            définir.
          </p>
          <UButton to="/login" color="primary" block> Aller à la connexion </UButton>
        </div>

        <form v-else class="space-y-4" @submit.prevent="onSubmit">
          <UFormField label="Mot de passe (8 caractères min.)" required>
            <GoupixDexPasswordInput v-model="password" autocomplete="new-password" required />
          </UFormField>
          <UFormField label="Confirmer le mot de passe" required>
            <GoupixDexPasswordInput v-model="password2" autocomplete="new-password" required />
          </UFormField>
          <UButton type="submit" color="primary" block size="lg" :loading="submitting" icon="i-lucide-shield-check">
            Enregistrer mon mot de passe
          </UButton>
        </form>
      </UCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ComputedRef, Ref } from 'vue'
import logoUrl from '~/assets/images/logo-goupix-dev-256x256.png'
import type { PasswordSetupInfo } from '~/composables/useAccessRequests'

definePageMeta({ layout: 'auth' })

useGoupixPageSeo(
  'Définir mon mot de passe',
  'Définissez votre mot de passe GoupixDex via le lien sécurisé envoyé par votre administrateur.',
)

const route = useRoute()
const { fetchPasswordSetupInfo, completePasswordSetup } = useAccessRequests()
const toast = useToast()

const info: Ref<PasswordSetupInfo | null> = ref(null)
const loadingInfo: Ref<boolean> = ref(true)
const loadError: Ref<string | null> = ref(null)
const password: Ref<string> = ref('')
const password2: Ref<string> = ref('')
const submitting: Ref<boolean> = ref(false)
const success: Ref<boolean> = ref(false)

const token: ComputedRef<string> = computed(() => String(route.params.token ?? ''))

async function load(): Promise<void> {
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

async function onSubmit(): Promise<void> {
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

onMounted((): void => {
  void load()
})
</script>
