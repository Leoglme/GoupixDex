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

/** Pages définissent leur propre titre / description ; valeurs par défaut avant navigation. */
const fallbackDescription
  = 'GoupixDex automatise la vente de vos cartes Pokémon TCG : scan, prix Cardmarket et TCGPlayer, stock, publication Vinted et marges.'

useSeoMeta({
  title: 'GoupixDex',
  description: fallbackDescription,
  ogTitle: 'GoupixDex',
  ogDescription: fallbackDescription,
  ogSiteName: 'GoupixDex',
  ogImage: '/logo-goupix-dev-256x256.png',
  applicationName: 'GoupixDex',
  twitterTitle: 'GoupixDex',
  twitterDescription: fallbackDescription,
  twitterCard: 'summary_large_image'
})
</script>

<template>
  <UApp>
    <DesktopUpdaterPanel />
    <NuxtLoadingIndicator />

    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </UApp>
</template>
