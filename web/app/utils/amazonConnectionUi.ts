import type { AmazonSessionResponse, AmazonSessionState } from '~/types/amazonInvites'

export type AmazonConnectionBadgeColor = 'success' | 'warning' | 'error' | 'neutral' | 'info'

export interface AmazonConnectionBadge {
  label: string
  color: AmazonConnectionBadgeColor
}

/**
 * Libellé + couleur de badge pour l’état de session Amazon (worker local).
 */
export function amazonSessionBadge(session: AmazonSessionResponse | null): AmazonConnectionBadge {
  if (!session) {
    return { label: 'État inconnu', color: 'neutral' }
  }
  const map: Record<AmazonSessionState, AmazonConnectionBadge> = {
    ready: { label: 'Connecté', color: 'success' },
    needs_login: { label: 'Non connecté', color: 'warning' },
    busy: { label: 'Occupé', color: 'info' },
    error: { label: 'Erreur session', color: 'error' },
  }
  return map[session.state] ?? { label: 'État inconnu', color: 'neutral' }
}
