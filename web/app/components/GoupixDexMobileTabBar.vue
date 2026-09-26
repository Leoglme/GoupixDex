<template>
  <nav
    class="standalone:max-lg:block fixed inset-x-0 bottom-0 z-30 hidden border-t border-(--app-line) bg-(--app-bg) pt-1 pb-[max(1.5rem,env(safe-area-inset-bottom))]"
    aria-label="Navigation rapide"
  >
    <div class="flex h-14 items-stretch">
      <GoupixDexMobileTabBarTab
        icon="i-lucide-layout-dashboard"
        to="/dashboard"
        :is-active="isDashboardActive"
        aria-label="Tableau de bord"
      />
      <GoupixDexMobileTabBarTab
        icon="i-lucide-album"
        to="/collection"
        :is-active="isCollectionSectionActive"
        aria-label="Ma collection"
      />

      <div class="flex w-22 shrink-0 items-center justify-center">
        <button
          type="button"
          class="text-primary-950 flex size-15 -translate-y-2.5 items-center justify-center rounded-full bg-(--app-accent) transition-opacity [-webkit-tap-highlight-color:transparent] active:opacity-80"
          aria-label="Scanner une carte"
          @click="openCardScanner()"
        >
          <UIcon name="i-lucide-scan-line" class="size-7" />
        </button>
      </div>

      <GoupixDexMobileTabBarTab
        icon="i-lucide-package"
        to="/articles"
        :is-active="isArticlesSectionActive"
        aria-label="Mes articles"
      />
      <GoupixDexMobileTabBarTab
        icon="i-lucide-search"
        :is-active="isPaletteOpen"
        aria-label="Rechercher"
        @click="openPalette()"
      />
    </div>
  </nav>
</template>

<script lang="ts" setup>
import type { ComputedRef, Ref } from 'vue'
import type { RouteLocationNormalizedLoaded } from 'vue-router'
import type { CardScannerShortcut } from '~/types/CardScannerShortcut'
import { useOpenCardScanner } from '~/composables/useOpenCardScanner'

const route: RouteLocationNormalizedLoaded = useRoute()
const { isOpen: isPaletteOpen, open: openPalette }: { isOpen: Ref<boolean>; open: () => void } = useCommandPalette()
const { openCardScanner }: CardScannerShortcut = useOpenCardScanner()

const isCollectionSectionActive: ComputedRef<boolean> = computed(
  (): boolean =>
    (route.path.startsWith('/collection') && !route.path.startsWith('/collection/scan')) ||
    route.path.startsWith('/classeurs'),
)
const isArticlesSectionActive: ComputedRef<boolean> = computed(
  (): boolean => route.path.startsWith('/articles') || route.path.startsWith('/shipping-labels'),
)
const isDashboardActive: ComputedRef<boolean> = computed((): boolean => route.path.startsWith('/dashboard'))
</script>
