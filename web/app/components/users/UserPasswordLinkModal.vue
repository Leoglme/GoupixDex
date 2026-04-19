<script setup lang="ts">
import type { PasswordSetupLink } from '~/composables/useUsers'

const props = defineProps<{
  modelValue: boolean
  user: { id: number, email: string } | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const open = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v)
})

const { generatePasswordLink } = useUsers()
const toast = useToast()

const link = ref<PasswordSetupLink | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

async function regenerate() {
  if (!props.user) {
    return
  }
  loading.value = true
  error.value = null
  try {
    link.value = await generatePasswordLink(props.user.id)
  } catch (e) {
    error.value = apiErrorMessage(e)
  } finally {
    loading.value = false
  }
}

watch(open, (v) => {
  if (v && props.user) {
    link.value = null
    regenerate()
  }
})

async function copy() {
  if (!link.value) {
    return
  }
  try {
    await navigator.clipboard.writeText(link.value.setup_url)
    toast.add({ title: 'Lien copié', color: 'success' })
  } catch {
    toast.add({ title: 'Copie impossible', color: 'error' })
  }
}

const expiresLabel = computed(() => {
  if (!link.value?.expires_at) {
    return ''
  }
  const d = new Date(link.value.expires_at)
  if (Number.isNaN(d.getTime())) {
    return ''
  }
  return d.toLocaleString('fr-FR', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
})
</script>

<template>
  <UModal
    v-model:open="open"
    title="Lien de définition du mot de passe"
    :description="user ? `Pour ${user.email}` : ''"
  >
    <template #body>
      <div class="space-y-4">
        <p class="text-sm text-muted">
          Envoyez ce lien à l'utilisateur. Il pourra définir son mot de passe GoupixDex en y accédant.
          Le lien devient inutilisable après une première sauvegarde réussie.
        </p>

        <div v-if="loading" class="flex items-center gap-2 text-sm text-muted">
          <UIcon name="i-lucide-loader-2" class="size-4 animate-spin" />
          Génération du lien…
        </div>

        <UAlert
          v-else-if="error"
          color="error"
          variant="subtle"
          icon="i-lucide-circle-alert"
          :title="error"
        />

        <template v-else-if="link">
          <UFormField label="Lien">
            <div class="flex gap-2">
              <UInput
                :model-value="link.setup_url"
                readonly
                class="w-full font-mono text-xs"
                @focus="(e: FocusEvent) => (e.target as HTMLInputElement).select()"
              />
              <UButton
                color="primary"
                icon="i-lucide-copy"
                @click="copy"
              >
                Copier
              </UButton>
            </div>
          </UFormField>

          <p v-if="expiresLabel" class="text-xs text-muted">
            Expire le {{ expiresLabel }}.
          </p>
        </template>
      </div>
    </template>
    <template #footer>
      <div class="flex w-full justify-between gap-2">
        <UButton
          color="neutral"
          variant="ghost"
          :disabled="loading"
          @click="regenerate"
        >
          <UIcon name="i-lucide-refresh-cw" class="size-4 mr-1.5" />
          Regénérer
        </UButton>
        <UButton
          color="primary"
          variant="soft"
          @click="open = false"
        >
          Fermer
        </UButton>
      </div>
    </template>
  </UModal>
</template>
