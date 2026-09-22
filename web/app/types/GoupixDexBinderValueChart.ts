/** Types du composant GoupixDexBinderValueChart (courbes valeur totale vs possédé). */

import type { BinderValuePeriod, BinderValueTimelinePoint } from '~/types/binders'

export interface GoupixDexBinderValueChartProps {
  points: BinderValueTimelinePoint[]
  period: BinderValuePeriod
}
