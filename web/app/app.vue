<script setup lang="ts">
const colorMode = useColorMode()

const color = computed(() => colorMode.value === 'dark' ? '#1b1718' : 'white')

useHead({
  meta: [
    { charset: 'utf-8' },
    { name: 'viewport', content: 'width=device-width, initial-scale=1' },
    { key: 'theme-color', name: 'theme-color', content: color },
    { name: 'apple-mobile-web-app-title', content: 'GoupixDex' }
  ],
  link: [
    { rel: 'icon', href: '/favicon.ico' },
    { rel: 'manifest', href: '/site.webmanifest' }
  ],
  htmlAttrs: {
    lang: 'fr'
  }
})

const title = 'GoupixDex — Automatisation vente cartes Pokémon TCG sur Vinted'
const description = 'GoupixDex automatise la vente de vos cartes Pokémon TCG : scan, prix Cardmarket & TCGPlayer, publication Vinted et suivi des marges. Scannez vos cartes, le reste s\'enchaîne.'

useSeoMeta({
  title,
  description,
  ogTitle: title,
  ogDescription: description,
  ogImage: '/logo-goupix-dev-256x256.png',
  applicationName: 'GoupixDex',
  twitterCard: 'summary_large_image',
  keywords: 'pokémon tcg, vinted, automatisation, cardmarket, tcgplayer, vente cartes pokémon, scan carte, goupixdex'
})
</script>

<template>
  <UApp>
    <NuxtLoadingIndicator />

    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </UApp>
</template>
