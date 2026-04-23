<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'

useDashboard()

const open = ref(false)
const { isDesktopApp } = useDesktopRuntime()
const { me, refreshMe } = useAuth()

if (import.meta.client && !me.value) {
  refreshMe()
}

/**
 * Journal des publications : Vinted + eBay (SSE). Catalogue : extensions / cartes (création).
 * Télécharger l'app : web uniquement. Le lien Utilisateurs n'apparaît que pour l'admin.
 */
const links = computed<NavigationMenuItem[][]>(() => {
  const items: NavigationMenuItem[] = [
    {
      label: 'Tableau de bord',
      icon: 'i-lucide-layout-dashboard',
      to: '/dashboard',
      onSelect: () => { open.value = false }
    },
    {
      label: 'Mon stock',
      icon: 'i-lucide-package',
      to: '/articles/stock',
      onSelect: () => { open.value = false }
    },
    {
      label: 'Catalogue',
      icon: 'i-lucide-library',
      to: '/articles/catalog',
      onSelect: () => { open.value = false }
    },
    {
      label: 'Articles',
      icon: 'i-lucide-store',
      to: '/articles',
      onSelect: () => { open.value = false }
    },
    {
      label: 'Journal des publications',
      icon: 'i-lucide-scroll-text',
      to: '/articles/listing-logs',
      onSelect: () => { open.value = false }
    },
    {
      label: 'Prix du marché',
      icon: 'i-lucide-trending-up',
      to: '/market',
      onSelect: () => { open.value = false }
    },
    {
      label: 'Étiquettes d\'envoi',
      icon: 'i-lucide-mailbox',
      to: '/shipping-labels',
      onSelect: () => { open.value = false }
    }
  ]

  if (me.value?.is_admin) {
    items.push({
      label: 'Utilisateurs',
      icon: 'i-lucide-users',
      to: '/users',
      onSelect: () => { open.value = false }
    })
  }

  if (!isDesktopApp.value) {
    items.push({
      label: 'Télécharger l\'app',
      icon: 'i-lucide-download',
      to: '/downloads',
      onSelect: () => { open.value = false }
    })
  }

  items.push({
    label: 'Paramètres',
    icon: 'i-lucide-settings',
    to: '/settings',
    onSelect: () => { open.value = false }
  })

  return [items]
})

const groups = computed(() => [{
  id: 'links',
  label: 'Navigation',
  items: links.value.flat().map(item => ({
    label: item.label,
    icon: item.icon,
    to: item.to
  }))
}])

function navMenuUi(collapsed: boolean) {
  return {
    root: 'gap-2',
    list: 'flex flex-col gap-y-2.5',
    item: 'shrink-0',
    link: collapsed ? 'justify-center' : ''
  }
}
</script>

<template>
  <UDashboardGroup unit="rem">
    <UDashboardSidebar
      id="default"
      v-model:open="open"
      collapsible
      resizable
      class="bg-elevated/25"
      :ui="{
        header: 'shrink-0',
        body: 'min-h-0',
        footer: 'lg:border-t lg:border-default shrink-0'
      }"
    >
      <template #header="{ collapsed }">
        <BrandHeader :collapsed="collapsed" />
      </template>

      <template #default="{ collapsed }">
        <UNavigationMenu
          :collapsed="collapsed"
          :items="links[0]"
          orientation="vertical"
          tooltip
          popover
          class="px-0.5"
          :ui="navMenuUi(collapsed)"
        />
      </template>

      <template #footer="{ collapsed }">
        <UserMenu :collapsed="collapsed" />
      </template>
    </UDashboardSidebar>

    <UDashboardSearch :groups="groups" />

    <slot />

    <BrowserMissingModal v-if="isDesktopApp" />
  </UDashboardGroup>
</template>
