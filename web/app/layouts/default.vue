<template>
  <UDashboardGroup unit="rem">
    <UDashboardSidebar
      id="default"
      v-model:open="open"
      collapsible
      resizable
      :default-size="17.5"
      :min-size="14"
      :max-size="24"
      class="bg-(--app-surface)"
      :ui="{
        header: 'shrink-0 border-b border-(--app-line)',
        body: 'min-h-0',
        footer: 'lg:border-t lg:border-(--app-line) shrink-0',
      }"
    >
      <template #header="{ collapsed }">
        <GoupixDexBrandHeader :collapsed="collapsed" />
      </template>

      <template #default="{ collapsed }">
        <button
          v-if="!collapsed"
          type="button"
          class="mb-3 flex w-full cursor-pointer items-center justify-between rounded-lg border border-(--app-line) bg-(--app-bg) px-2.5 py-1.5 text-xs text-(--app-faint) transition-colors hover:border-(--app-ink-soft) hover:text-(--app-ink-soft)"
          @click="openPalette()"
        >
          <span class="flex items-center gap-2">
            <UIcon name="i-lucide-search" class="h-3.5 w-3.5" />
            Rechercher…
          </span>
          <span
            class="rounded border border-(--app-line) bg-(--app-surface) px-1 py-0.5 font-mono text-[9px] uppercase"
          >
            Ctrl K
          </span>
        </button>
        <UButton
          v-else
          color="neutral"
          variant="ghost"
          icon="i-lucide-search"
          class="mb-3 justify-center"
          aria-label="Rechercher (Ctrl+K)"
          @click="openPalette()"
        />
        <nav class="flex flex-col gap-5" aria-label="Navigation principale">
          <div v-for="group in navGroups" :key="group.heading">
            <p v-if="!collapsed" class="app-label mb-1.5 px-2.5 !text-[0.6rem]">{{ group.heading }}</p>
            <UNavigationMenu
              :collapsed="collapsed"
              :items="group.items"
              orientation="vertical"
              tooltip
              popover
              class="px-0.5"
              :ui="navMenuUi(collapsed)"
            />
          </div>
        </nav>
      </template>

      <template #footer="{ collapsed }">
        <GoupixDexUserMenu :collapsed="collapsed" />
      </template>
    </UDashboardSidebar>

    <GoupixDexCommandPalette />

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
import type { AppSidebarNavGroup } from '~/types/AppNavigation'

useDashboard()

const route = useRoute()
const open: Ref<boolean> = ref(false)
const { open: openPalette } = useCommandPalette()
const { isDesktopApp, restartLocalWorkers, syncDevDatabaseFromProd } = useDesktopRuntime()
const toast = useToast()
const workersRestarting: Ref<boolean> = ref(false)
const dbSyncLoading: Ref<boolean> = ref(false)

const showDevWorkerControls = computed(() => import.meta.dev && Boolean(isDesktopApp.value))

/**
 * Restarts the local Python worker sidecars (Tauri only) and reports the outcome as a toast.
 * @returns Resolves when the restart request completed.
 */
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

/**
 * Replaces the local dev database with a fresh production dump after user confirmation.
 * @returns Resolves when the sync finished or was cancelled.
 */
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

/**
 * Closes the mobile sidebar after a navigation item has been selected.
 */
function closeSidebar(): void {
  open.value = false
}

/**
 * Builds one sidebar link with an explicit active state computed from the current route,
 * so grouped pages (tabs spanning several routes) highlight a single menu entry.
 * @param label - Visible label of the entry.
 * @param icon - Iconify icon name.
 * @param to - Target route.
 * @param activePrefixes - Route prefixes that mark this entry as active.
 * @param exclude - Route prefixes that must NOT activate this entry (e.g. a sibling entry's route).
 * @returns The navigation menu item.
 */
function navLink(
  label: string,
  icon: string,
  to: string,
  activePrefixes: string[],
  exclude: string[] = [],
): NavigationMenuItem {
  const path: string = route.path
  const excluded: boolean = exclude.some((prefix: string): boolean => path.startsWith(prefix))
  const active: boolean = !excluded && activePrefixes.some((prefix: string): boolean => path.startsWith(prefix))
  return { label, icon, to, active, onSelect: closeSidebar }
}

const navGroups: ComputedRef<AppSidebarNavGroup[]> = computed((): AppSidebarNavGroup[] => {
  const sellingItems: NavigationMenuItem[] = [
    navLink('Mes articles', 'i-lucide-package', '/articles', ['/articles']),
    navLink('Marché eBay', 'i-lucide-trending-up', '/market', ['/market', '/top-ventes-ebay']),
    navLink("Étiquettes d'envoi", 'i-lucide-mailbox', '/shipping-labels', ['/shipping-labels']),
  ]

  const collectionItems: NavigationMenuItem[] = [
    navLink('Ma collection', 'i-lucide-album', '/collection', ['/collection'], ['/collection/scan']),
    // Scanner = phone → web flow; on desktop the page shows a QR code to open it on the phone.
    navLink('Scanner mes cartes', 'i-lucide-scan-line', '/collection/scan', ['/collection/scan']),
  ]

  // Cardmarket basket optimization left the menu on purpose: it is reachable from
  // the "Commandes Cardmarket" page header (and the command palette) instead.
  const purchasesItems: NavigationMenuItem[] = [
    navLink('Commandes Cardmarket', 'i-lucide-file-text', '/orders', ['/orders']),
  ]
  if (isDesktopApp.value) {
    // Relies on the local nodriver worker, which only exists in the Tauri app.
    purchasesItems.push(navLink('Invitations Amazon', 'i-simple-icons-amazon', '/amazon-invites', ['/amazon-invites']))
  }

  const result: AppSidebarNavGroup[] = [
    {
      heading: 'Pilotage',
      items: [navLink('Tableau de bord', 'i-lucide-layout-dashboard', '/dashboard', ['/dashboard'])],
    },
    { heading: 'Vente', items: sellingItems },
    { heading: 'Collection', items: collectionItems },
    { heading: 'Achats', items: purchasesItems },
  ]

  if (me.value?.is_admin) {
    result.push({
      heading: 'Administration',
      items: [navLink('Utilisateurs', 'i-lucide-users', '/users', ['/users'])],
    })
  }

  return result
})

/**
 * Per-state classes of the sidebar navigation menu.
 * @param collapsed - Whether the sidebar is collapsed to icons only.
 * @returns The `ui` overrides for UNavigationMenu.
 */
function navMenuUi(collapsed: boolean): { root: string; list: string; item: string; link: string } {
  return {
    root: 'gap-1',
    list: 'flex flex-col gap-y-0.5',
    item: 'shrink-0',
    link: collapsed ? 'justify-center' : 'gap-2.5 rounded-lg py-1.5',
  }
}

// Précharge le moteur de scan (worker + modèles + index, ~50 MB une seule
// fois puis cache navigateur) dès l'ouverture de l'app : à l'arrivée sur la
// caméra il est déjà prêt — ressenti instantané, comme une app native qui
// embarque son modèle à l'installation.
const scanEmbed = useScanEmbedIndex()

onMounted((): void => {
  setTimeout((): void => {
    void scanEmbed.load()
  }, 1500)
})
</script>
