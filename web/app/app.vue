<template>
  <UApp>
    <GoupixDexDesktopUpdaterPanel />
    <NuxtLoadingIndicator />

    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </UApp>
</template>

<script setup lang="ts">
import type { ComputedRef } from 'vue'

const colorMode: ReturnType<typeof useColorMode> = useColorMode()

const color: ComputedRef<string> = computed((): string => (colorMode.value === 'dark' ? '#1b1718' : 'white'))

useHead({
  meta: [
    { charset: 'utf-8' },
    { name: 'viewport', content: 'width=device-width, initial-scale=1' },
    { key: 'theme-color', name: 'theme-color', content: color },
    // PWA — installable app on iPhone/Android home screen (standalone).
    { name: 'mobile-web-app-capable', content: 'yes' },
    { name: 'apple-mobile-web-app-capable', content: 'yes' },
    { name: 'apple-mobile-web-app-status-bar-style', content: 'black-translucent' },
    { name: 'apple-mobile-web-app-title', content: 'GoupixDex' },
  ],
  link: [
    { rel: 'icon', type: 'image/png', sizes: '32x32', href: '/favicon-32x32.png' },
    { rel: 'icon', type: 'image/png', sizes: '16x16', href: '/favicon-16x16.png' },
    { rel: 'icon', href: '/favicon.ico' },
    { rel: 'manifest', href: '/site.webmanifest' },
    { rel: 'apple-touch-icon', sizes: '180x180', href: '/apple-touch-icon.png' },
  ],
  htmlAttrs: {
    lang: 'fr',
  },
})

/** Pages set their own title/description; defaults before navigation. */
const fallbackDescription: string =
  'GoupixDex automatise la vente de vos cartes Pokémon TCG : scan, prix Cardmarket et TCGPlayer, stock, publication Vinted et marges.'

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
  twitterCard: 'summary_large_image',
})
</script>
