// app/types/AppNavigation.ts
import type { NavigationMenuItem } from '@nuxt/ui'

/**
 * One titled group of links in the dashboard sidebar.
 */
export type AppSidebarNavGroup = {
  heading: string
  items: NavigationMenuItem[]
}
