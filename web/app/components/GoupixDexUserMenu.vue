<template>
  <GoupixDexProfileDrawer :open="profileDrawerOpen" @close="closeProfileDrawer" />

  <UDropdownMenu
    :items="items"
    :content="{ align: 'center', collisionPadding: 12 }"
    :ui="{ content: collapsed ? 'w-48' : 'w-(--reka-dropdown-menu-trigger-width)', item: 'cursor-pointer' }"
  >
    <button
      type="button"
      class="text-highlighted hover:bg-elevated/80 data-[state=open]:bg-elevated flex w-full cursor-pointer items-center rounded-lg transition-colors"
      :class="collapsed ? 'justify-center px-2 py-2' : 'gap-2.5 px-2 py-2 text-left'"
      :aria-label="collapsed ? 'Menu compte et paramètres' : undefined"
    >
      <UIcon v-if="collapsed" name="i-lucide-circle-user" class="text-muted size-5 shrink-0" />
      <template v-else>
        <span class="min-w-0 flex-1 truncate text-sm font-medium">{{ accountLabel ?? 'Compte' }}</span>
        <UIcon name="i-lucide-chevrons-up-down" class="text-muted size-3.5 shrink-0" />
      </template>
    </button>
  </UDropdownMenu>
</template>

<script setup lang="ts">
import type { ComputedRef } from 'vue'
import type { DropdownMenuItem } from '@nuxt/ui'

defineProps<{
  collapsed?: boolean
}>()

const colorMode = useColorMode()
const { me, logout } = useAuth()
const { isDesktopApp } = useDesktopRuntime()
const { profileDrawerOpen, openProfileDrawer, closeProfileDrawer } = useProfileDrawer()

const accountLabel = computed(() => {
  const name = me.value?.full_name?.trim()
  if (name) {
    return name
  }
  return me.value?.email ?? 'Compte'
})

const items: ComputedRef<DropdownMenuItem[][]> = computed(() => [
  [
    {
      type: 'label',
      label: me.value?.full_name?.trim() || me.value?.email || 'Compte',
      icon: 'i-lucide-user',
    },
  ],
  [
    {
      label: 'Mon profil',
      icon: 'i-lucide-user-pen',
      onSelect() {
        openProfileDrawer()
      },
    },
    {
      label: 'Paramètres',
      icon: 'i-lucide-settings',
      to: '/settings',
    },
    ...(me.value?.is_admin
      ? [
          {
            label: 'Utilisateurs',
            icon: 'i-lucide-users',
            to: '/users',
          },
        ]
      : []),
    ...(isDesktopApp.value
      ? []
      : [
          {
            label: "Télécharger l'app",
            icon: 'i-lucide-hard-drive-download',
            to: '/downloads',
          },
        ]),
  ],
  [
    {
      label: 'Apparence',
      icon: 'i-lucide-sun-moon',
      children: [
        {
          label: 'Clair',
          icon: 'i-lucide-sun',
          class: 'cursor-pointer',
          type: 'checkbox',
          checked: colorMode.value === 'light',
          onSelect(e: Event) {
            e.preventDefault()
            colorMode.preference = 'light'
          },
        },
        {
          label: 'Sombre',
          icon: 'i-lucide-moon',
          class: 'cursor-pointer',
          type: 'checkbox',
          checked: colorMode.value === 'dark',
          onSelect(e: Event) {
            e.preventDefault()
            colorMode.preference = 'dark'
          },
        },
      ],
    },
  ],
  [
    {
      label: 'Déconnexion',
      icon: 'i-lucide-log-out',
      async onSelect() {
        await logout()
      },
    },
  ],
])
</script>
