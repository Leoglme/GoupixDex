<template>
  <GoupixDexAlert
    v-if="session || loading"
    :variant="alertVariant"
    :title="title"
    :description="description || undefined"
    :icon="alertIcon"
    :icon-class="loading ? 'animate-spin' : ''"
  >
    <template v-if="session?.state !== 'ready'" #actions>
      <UButton
        to="/settings/marketplaces#cardmarket-connection"
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
import type { CardmarketSessionResponse, CardmarketSessionState } from '~/types/CardmarketSession'

const props = defineProps<{
  session: CardmarketSessionResponse | null
  loading: boolean
}>()

const alertVariant = computed((): GoupixDexAlertVariant => {
  if (props.loading || !props.session) {
    return 'info'
  }
  const m: Record<CardmarketSessionState, GoupixDexAlertVariant> = {
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
  return 'i-lucide-shopping-cart'
})

const title = computed(() => {
  if (props.loading) {
    return 'Chargement…'
  }
  if (!props.session) {
    return ''
  }
  const t: Record<CardmarketSessionState, string> = {
    ready: 'Compte Cardmarket connecté',
    needs_login: 'Connexion Cardmarket recommandée',
    busy: 'Connexion Cardmarket en cours…',
    error: 'Connexion Cardmarket interrompue',
  }
  return t[props.session.state] ?? ''
})

const description = computed(() => {
  if (props.loading) {
    return 'Vérification de votre session Cardmarket…'
  }
  if (!props.session) {
    return ''
  }
  const s = props.session.state
  if (s === 'ready') {
    const who = props.session.username ? `Connecté en tant que ${props.session.username}` : 'Session active'
    if (props.session.credit_eur != null) {
      const fmt = new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(
        props.session.credit_eur,
      )
      return `${who} · crédit ${fmt}. Vos analyses utiliseront cette session pour limiter les blocages Cloudflare.`
    }
    return `${who}. Vos analyses utiliseront cette session pour limiter les blocages Cloudflare.`
  }
  if (s === 'needs_login') {
    return 'Connectez votre compte Cardmarket dans les paramètres marketplace : cela évite la plupart des blocages Cloudflare et accélère le scraping.'
  }
  if (s === 'busy') {
    return 'Chrome est ouvert pour la connexion Cardmarket. Identifiez-vous puis revenez ici (la détection est automatique).'
  }
  return 'Réessayez plus tard. Si le problème continue, ouvrez Chrome depuis les paramètres pour vérifier la session.'
})
</script>
