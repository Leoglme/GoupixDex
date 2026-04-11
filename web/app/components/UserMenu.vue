<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui'

defineProps<{
  collapsed?: boolean
}>()

const colorMode = useColorMode()
const { me, logout } = useAuth()

const items = computed<DropdownMenuItem[][]>(() => [
  [{
    type: 'label',
    label: me.value?.email ?? 'Compte',
    icon: 'i-lucide-user'
  }],
  [{
    label: 'Paramètres',
    icon: 'i-lucide-settings',
    to: '/settings'
  }],
  [{
    label: 'Apparence',
    icon: 'i-lucide-sun-moon',
    children: [{
      label: 'Clair',
      icon: 'i-lucide-sun',
      class: 'cursor-pointer',
      type: 'checkbox',
      checked: colorMode.value === 'light',
      onSelect(e: Event) {
        e.preventDefault()
        colorMode.preference = 'light'
      }
    }, {
      label: 'Sombre',
      icon: 'i-lucide-moon',
      class: 'cursor-pointer',
      type: 'checkbox',
      checked: colorMode.value === 'dark',
      onSelect(e: Event) {
        e.preventDefault()
        colorMode.preference = 'dark'
      }
    }]
  }],
  [{
    label: 'Déconnexion',
    icon: 'i-lucide-log-out',
    async onSelect() {
      await logout()
    }
  }]
])
</script>

<template>
  <UDropdownMenu
    :items="items"
    :content="{ align: 'center', collisionPadding: 12 }"
    :ui="{ content: collapsed ? 'w-48' : 'w-(--reka-dropdown-menu-trigger-width)', item: 'cursor-pointer' }"
  >
    <UButton
      color="neutral"
      variant="ghost"
      block
      :square="collapsed"
      class="data-[state=open]:bg-elevated"
      :class="[!collapsed && 'py-2']"
      :icon="collapsed ? 'i-lucide-circle-user' : undefined"
      :label="collapsed ? undefined : (me?.email ?? 'Compte')"
      :trailing-icon="collapsed ? undefined : 'i-lucide-chevrons-up-down'"
      :aria-label="collapsed ? 'Menu compte et paramètres' : undefined"
    />
  </UDropdownMenu>
</template>
