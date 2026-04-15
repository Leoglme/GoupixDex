<script setup lang="ts">
import type { NuxtError } from '#app'

defineProps<{
  error: NuxtError
}>()

useGoupixPageSeo(
  'Page introuvable',
  'Cette page GoupixDex n’existe pas ou a été déplacée. Retournez au tableau de bord ou à l’accueil.'
)

useHead({
  htmlAttrs: {
    lang: 'fr'
  }
})
</script>

<template>
  <UApp>
    <UError :error="error" />
  </UApp>
</template>
