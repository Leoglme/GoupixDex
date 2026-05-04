/**
 * Props pour le composant ``GoupixDexAmazonRefreshProgress.vue``.
 */
export interface GoupixDexAmazonRefreshProgressProps {
  /** Most recent status summary line (optional subtitle under the title). */
  phaseHint?: string
  /** Scrollable activity log (newest lines appended). */
  logLines: readonly string[]
}
