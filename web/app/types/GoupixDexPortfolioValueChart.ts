/** Types du composant GoupixDexPortfolioValueChart (courbes valeur marché vs achat). */

import type { PortfolioPeriod, PortfolioTimelinePoint } from '~/composables/usePortfolio'

export interface GoupixDexPortfolioValueChartProps {
  /** Points datés à tracer (marché, achat), triés par date croissante. */
  points: PortfolioTimelinePoint[]
  /** Période sélectionnée, pour le format des dates de l'axe X. */
  period: PortfolioPeriod
}
