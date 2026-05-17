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
        footer: 'lg:border-t lg:border-default shrink-0',
      }"
    >
      <template #header="{ collapsed }">
        <GoupixDexBrandHeader :collapsed="collapsed" />
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
        <GoupixDexUserMenu :collapsed="collapsed" />
      </template>
    </UDashboardSidebar>

    <UDashboardSearch :groups="groups" />

    <slot />

    <GoupixDexBrowserMissingModal v-if="isDesktopApp" />

    <div
      v-if="showDevWorkerControls"
      class="border-default bg-elevated/95 fixed right-3 bottom-3 z-[100] flex max-w-[min(100vw-1.5rem,22rem)] flex-col gap-2 rounded-lg border px-2 py-1.5 shadow-lg sm:max-w-none sm:flex-row sm:items-center"
    >
      <span class="text-muted hidden text-xs sm:inline">Dev · workers</span>
      <div class="flex flex-wrap items-center gap-2">
        <UButton size="xs" color="neutral" variant="soft" :loading="workersRestarting" @click="onRestartWorkers">
          Redémarrer workers
        </UButton>
        <UButton
          size="xs"
          color="warning"
          variant="soft"
          :loading="dbSyncLoading"
          title="Requires web/.env.sync. Without local SQL clients, Docker Desktop is enough (mariadb:11) — see .env.sync.example"
          @click="onSyncDevDb"
        >
          Sync DB prod → dev
        </UButton>
      </div>
    </div>
  </UDashboardGroup>
</template>

<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'
import type { ComputedRef, Ref } from 'vue'

useDashboard()

const open: Ref<boolean> = ref(false)
const { isDesktopApp, restartLocalWorkers, syncDevDatabaseFromProd } = useDesktopRuntime()
const toast = useToast()
const workersRestarting: Ref<boolean> = ref(false)
const dbSyncLoading: Ref<boolean> = ref(false)

const showDevWorkerControls = computed(() => import.meta.dev && Boolean(isDesktopApp.value))

async function onRestartWorkers(): Promise<void> {
  workersRestarting.value = true
  try {
    await restartLocalWorkers()
    toast.add({ title: 'Workers locaux redémarrés', color: 'success' })
  } catch (e: unknown) {
    toast.add({
      title: 'Redémarrage workers',
      description: e instanceof Error ? e.message : String(e),
      color: 'error',
    })
  } finally {
    workersRestarting.value = false
  }
}

async function onSyncDevDb(): Promise<void> {
  const ok = window.confirm(
    'Replace all data in the local Docker database with a prod dump?\n' +
      'Stop the api container (`docker compose stop api`) if import fails (connections).\n' +
      'Configure web/.env.sync — see web/.env.sync.example.',
  )
  if (!ok) {
    return
  }
  dbSyncLoading.value = true
  try {
    const msg = await syncDevDatabaseFromProd()
    toast.add({ title: 'Local database updated', description: msg, color: 'success' })
  } catch (e: unknown) {
    toast.add({
      title: 'Sync DB prod → dev',
      description: e instanceof Error ? e.message : String(e),
      color: 'error',
    })
  } finally {
    dbSyncLoading.value = false
  }
}

const { me, refreshMe } = useAuth()

if (import.meta.client && !me.value) {
  refreshMe()
}

const links: ComputedRef<NavigationMenuItem[][]> = computed(() => {
  const items: NavigationMenuItem[] = [
    {
      label: 'Tableau de bord',
      icon: 'i-lucide-layout-dashboard',
      to: '/dashboard',
      onSelect: () => {
        open.value = false
      },
    },
    {
      label: 'Mon stock',
      icon: 'i-lucide-package',
      to: '/articles/stock',
      onSelect: () => {
        open.value = false
      },
    },
    {
      label: 'Ma collection',
      icon: 'i-lucide-album',
      to: '/collection',
      onSelect: () => {
        open.value = false
      },
    },
    {
      label: 'Articles',
      icon: 'i-lucide-store',
      to: '/articles',
      onSelect: () => {
        open.value = false
      },
    },
    {
      label: 'Articles vendus',
      icon: 'i-lucide-badge-check',
      to: '/articles/sold',
      onSelect: () => {
        open.value = false
      },
    },
    {
      label: 'Commandes',
      icon: 'i-lucide-file-text',
      to: '/orders',
      onSelect: () => {
        open.value = false
      },
    },
    {
      label: 'Panier Cardmarket',
      icon: 'i-lucide-shopping-basket',
      to: '/panier-cardmarket',
      onSelect: () => {
        open.value = false
      },
    },
    {
      label: 'Prix du marché',
      icon: 'i-lucide-trending-up',
      to: '/market',
      onSelect: () => {
        open.value = false
      },
    },
    {
      label: 'Ventes terminées eBay',
      icon: 'i-simple-icons-ebay',
      to: '/top-ventes-ebay',
      onSelect: () => {
        open.value = false
      },
    },
    {
      label: 'Invitations Amazon',
      icon: 'i-simple-icons-amazon',
      to: '/amazon-invites',
      onSelect: () => {
        open.value = false
      },
    },
    {
      label: "Étiquettes d'envoi",
      icon: 'i-lucide-mailbox',
      to: '/shipping-labels',
      onSelect: () => {
        open.value = false
      },
    },
  ]

  if (me.value?.is_admin) {
    items.push({
      label: 'Utilisateurs',
      icon: 'i-lucide-users',
      to: '/users',
      onSelect: () => {
        open.value = false
      },
    })
  }

  if (!isDesktopApp.value) {
    items.push({
      label: "Télécharger l'app",
      icon: 'i-lucide-hard-drive-download',
      to: '/downloads',
      onSelect: () => {
        open.value = false
      },
    })
    // Scanner = flux téléphone → web ; la version desktop n'a pas de caméra
    // pertinente, donc on n'affiche le raccourci que dans le navigateur.
    items.push({
      label: 'Scanner mes cartes',
      icon: 'i-lucide-scan-line',
      to: '/collection/scan',
      onSelect: () => {
        open.value = false
      },
    })
  }

  return [items]
})

type SidebarSearchGroup = {
  id: string
  label: string
  items: Array<Pick<NavigationMenuItem, 'label' | 'icon' | 'to'>>
}

const groups: ComputedRef<SidebarSearchGroup[]> = computed(() => [
  {
    id: 'links',
    label: 'Navigation',
    items: links.value.flat().map((item) => ({
      label: item.label,
      icon: item.icon,
      to: item.to,
    })),
  },
])

function navMenuUi(collapsed: boolean): { root: string; list: string; item: string; link: string } {
  return {
    root: 'gap-2',
    list: 'flex flex-col gap-y-2.5',
    item: 'shrink-0',
    link: collapsed ? 'justify-center' : '',
  }
}
</script>
