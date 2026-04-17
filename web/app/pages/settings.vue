<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'

const route = useRoute()

const links = computed(() => {
  const path = route.path
  const isConfig = path === '/settings' || path === '/settings/'
  const isMarketplaces = path.startsWith('/settings/marketplaces')
  const isUsers = path.startsWith('/settings/users')
  return [[{
    label: 'Configuration',
    icon: 'i-lucide-user',
    to: '/settings',
    exact: true,
    active: isConfig
  }, {
    label: 'Marketplace',
    icon: 'i-lucide-store',
    to: '/settings/marketplaces',
    active: isMarketplaces
  }, {
    label: 'Utilisateurs',
    icon: 'i-lucide-users',
    to: '/settings/users',
    active: isUsers
  }]] as NavigationMenuItem[][]
})
</script>

<template>
  <UDashboardPanel id="settings">
    <template #header>
      <div
        class="flex flex-wrap items-center gap-2 border-b border-default px-4 py-2 sm:px-6"
      >
        <UDashboardSidebarCollapse />
        <UNavigationMenu
          :items="links"
          highlight
          class="-mx-1 min-w-0 flex-1"
        />
      </div>
    </template>

    <template #body>
      <div class="w-full p-4 sm:p-6">
        <NuxtPage />
      </div>
    </template>
  </UDashboardPanel>
</template>
