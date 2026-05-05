import type { AmazonSessionResponse, AmazonSessionState } from '~/types/amazonInvites'

export type AmazonConnectionBadgeColor = 'success' | 'warning' | 'error' | 'neutral' | 'info'

export interface AmazonConnectionBadge {
  label: string
  color: AmazonConnectionBadgeColor
}

/**
 * Badge label + color for Amazon session state (local worker).
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
