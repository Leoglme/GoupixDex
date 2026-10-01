<template>
  <footer class="border-t border-(--app-line) bg-(--app-surface)">
    <div class="mx-auto flex max-w-6xl flex-col gap-5 px-5 py-8 sm:px-8 md:flex-row md:items-center md:justify-between">
      <div class="flex items-center gap-2.5">
        <img :src="logoUrl" alt="GoupixDex" class="size-6 object-contain" width="24" height="24" />
        <span class="text-muted text-sm font-medium">© {{ currentYear }} GoupixDex · édité par Dibodev</span>
      </div>
      <nav aria-label="Informations et contact" class="text-muted flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
        <NuxtLink
          v-for="link in FOOTER_LINKS"
          :key="link.to"
          :to="link.to"
          class="transition-colors hover:text-(--app-ink)"
          active-class="text-(--app-ink)"
        >
          {{ link.label }}
        </NuxtLink>
      </nav>
    </div>
  </footer>
</template>

<script lang="ts" setup>
import type { LandingFooterLink } from '~/types/GoupixDexLandingFooter'
import logoUrl from '~/assets/images/logo-goupix-dev-256x256.png'

const currentYear: number = new Date().getFullYear()

const FOOTER_LINKS: LandingFooterLink[] = [
  { to: '/contact', label: 'Contact' },
  { to: '/legal', label: 'Mentions légales' },
  { to: '/privacy', label: 'Confidentialité' },
  { to: '/terms', label: 'CGU' },
  { to: '/request', label: "Demander l'accès" },
]
</script>
