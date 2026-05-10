import type { CardmarketSessionResponse, CardmarketSessionState } from '~/types/CardmarketSession'

export type CardmarketConnectionBadgeColor = 'success' | 'warning' | 'error' | 'neutral' | 'info'

export interface CardmarketConnectionBadge {
  label: string
  color: CardmarketConnectionBadgeColor
}

/**
 * Badge label + color for the Cardmarket session card / banner.
 * @param session - Worker response, or null when state is unknown.
 * @returns Pre-translated label + color.
 */
export function cardmarketSessionBadge(session: CardmarketSessionResponse | null): CardmarketConnectionBadge {
  if (!session) {
    return { label: 'État inconnu', color: 'neutral' }
  }
  const map: Record<CardmarketSessionState, CardmarketConnectionBadge> = {
    ready: { label: session.username ? `Connecté · ${session.username}` : 'Connecté', color: 'success' },
    needs_login: { label: 'Non connecté', color: 'warning' },
    busy: { label: 'Connexion en cours…', color: 'info' },
    error: { label: 'Erreur session', color: 'error' },
  }
  return map[session.state] ?? { label: 'État inconnu', color: 'neutral' }
}
