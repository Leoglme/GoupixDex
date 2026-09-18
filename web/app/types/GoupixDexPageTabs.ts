// app/types/GoupixDexPageTabs.ts

/**
 * One tab of a GoupixDexPageTabs strip. Tabs are links between sibling routes.
 */
export type GoupixDexPageTabItem = {
  label: string
  to: string
  icon?: string
  count?: number
}

/**
 * Props for the GoupixDexPageTabs component.
 */
export type GoupixDexPageTabsProps = {
  items: GoupixDexPageTabItem[]
}
