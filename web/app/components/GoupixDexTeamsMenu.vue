<template>
  <UDropdownMenu
    :items="items"
    :content="{ align: 'center', collisionPadding: 12 }"
    :ui="{ content: collapsed ? 'w-40' : 'w-(--reka-dropdown-menu-trigger-width)' }"
  >
    <UButton
      v-bind="{
        ...selectedTeam,
        label: collapsed ? undefined : selectedTeam?.label,
        trailingIcon: collapsed ? undefined : 'i-lucide-chevrons-up-down',
      }"
      color="neutral"
      variant="ghost"
      block
      :square="collapsed"
      class="data-[state=open]:bg-elevated"
      :class="[!collapsed && 'py-2']"
      :ui="{
        trailingIcon: 'text-dimmed',
      }"
    />
  </UDropdownMenu>
</template>

<script setup lang="ts">
import type { ComputedRef, Ref } from 'vue'
import type { DropdownMenuItem } from '@nuxt/ui'

type TeamListItem = {
  label: string
  avatar: { src: string; alt: string }
}

defineProps<{
  collapsed?: boolean
}>()

const teams: Ref<TeamListItem[]> = ref([
  {
    label: 'Nuxt',
    avatar: {
      src: 'https://github.com/nuxt.png',
      alt: 'Nuxt',
    },
  },
  {
    label: 'NuxtHub',
    avatar: {
      src: 'https://github.com/nuxt-hub.png',
      alt: 'NuxtHub',
    },
  },
  {
    label: 'NuxtLabs',
    avatar: {
      src: 'https://github.com/nuxtlabs.png',
      alt: 'NuxtLabs',
    },
  },
])
const selectedTeam: Ref<TeamListItem> = ref(teams.value[0]!)

const items: ComputedRef<DropdownMenuItem[][]> = computed(() => {
  return [
    teams.value.map((team) => ({
      ...team,
      onSelect() {
        selectedTeam.value = team
      },
    })),
    [
      {
        label: 'Create team',
        icon: 'i-lucide-circle-plus',
      },
      {
        label: 'Manage teams',
        icon: 'i-lucide-cog',
      },
    ],
  ]
})
</script>
