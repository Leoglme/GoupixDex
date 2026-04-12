<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'

useDashboard()

const open = ref(false)

const links = [[{
  label: 'Tableau de bord',
  icon: 'i-lucide-layout-dashboard',
  to: '/dashboard',
  onSelect: () => { open.value = false }
}, {
  label: 'Articles',
  icon: 'i-lucide-layers',
  to: '/articles',
  onSelect: () => { open.value = false }
}, {
  label: 'Journal Vinted',
  icon: 'i-lucide-scroll-text',
  to: '/articles/vinted-logs',
  onSelect: () => { open.value = false }
}, {
  label: 'Paramètres',
  icon: 'i-lucide-settings',
  to: '/settings',
  onSelect: () => { open.value = false }
}]] satisfies NavigationMenuItem[][]

const groups = computed(() => [{
  id: 'links',
  label: 'Navigation',
  items: links.flat()
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
  </UDashboardGroup>
</template>
