<template>
  <GoupixDexAlert
    v-if="session || loading"
    :variant="alertVariant"
    :title="title"
    :description="description || undefined"
    :icon="alertIcon"
    :icon-class="loading ? 'animate-spin' : ''"
  >
    <template v-if="session?.state === 'needs_login'" #actions>
      <UButton
        to="/settings/marketplaces#amazon-connection"
        size="xs"
        color="neutral"
        variant="subtle"
        icon="i-lucide-settings"
      >
        Paramètres marketplace
      </UButton>
    </template>
  </GoupixDexAlert>
</template>

<script setup lang="ts">
import type { GoupixDexAlertVariant } from '~/types/GoupixDexAlert'
import type { AmazonSessionResponse, AmazonSessionState } from '~/types/amazonInvites'

const props = defineProps<{
  session: AmazonSessionResponse | null
  loading: boolean
}>()

const alertVariant = computed((): GoupixDexAlertVariant => {
  if (props.loading || !props.session) {
    return 'info'
  }
  const m: Record<AmazonSessionState, GoupixDexAlertVariant> = {
    ready: 'success',
    needs_login: 'warning',
    busy: 'info',
    error: 'error',
  }
  return m[props.session.state] ?? 'info'
})

const alertIcon = computed(() => {
  if (props.loading) {
    return 'i-lucide-loader-circle'
  }
  return 'i-simple-icons-amazon'
})

const title = computed(() => {
  if (props.loading) {
    return 'Chargement…'
  }
  if (!props.session) {
    return ''
  }
  const t: Record<AmazonSessionState, string> = {
    ready: 'Compte synchronisé',
    needs_login: 'Connexion Amazon',
    busy: 'Un instant…',
    error: 'Connexion interrompue',
  }
  return t[props.session.state] ?? ''
})

/** User-friendly copy only — no raw API error details. */
const description = computed(() => {
  if (props.loading) {
    return 'Récupération de vos invitations…'
  }
  if (!props.session) {
    return ''
  }
  const s = props.session.state
  if (s === 'ready') {
    if (props.session.last_sync_at) {
      return `Dernière mise à jour : ${new Date(props.session.last_sync_at).toLocaleString('fr-FR')}`
    }
    return 'Vous pouvez actualiser la liste quand vous le souhaitez.'
  }
  if (s === 'needs_login') {
    return 'Connectez-vous à votre compte Amazon sur cet ordinateur, puis appuyez sur « Actualiser » pour afficher vos invitations.'
  }
  if (s === 'busy') {
    return 'Une opération est en cours. Réessayez dans quelques secondes.'
  }
  if (s === 'error') {
    return 'Réessayez plus tard. Si le problème continue, reconnectez-vous à GoupixDex ou contactez le support.'
  }
  return ''
})
</script>
