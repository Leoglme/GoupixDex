import type { LeboncoinSessionResponse, LeboncoinSessionState } from '~/composables/useLeboncoinWorker'

export type LeboncoinConnectionBadgeColor = 'success' | 'warning' | 'error' | 'neutral' | 'info'

export interface LeboncoinConnectionBadge {
  label: string
  color: LeboncoinConnectionBadgeColor
}

export function leboncoinSessionBadge(session: LeboncoinSessionResponse | null): LeboncoinConnectionBadge {
  if (!session) {
    return { label: 'État inconnu', color: 'neutral' }
  }
  const map: Record<LeboncoinSessionState, LeboncoinConnectionBadge> = {
    ready: { label: 'Connecté', color: 'success' },
    needs_login: { label: 'Non connecté', color: 'warning' },
    busy: { label: 'Chrome ouvert', color: 'info' },
    unreadable: { label: 'Profil verrouillé', color: 'warning' },
  }
  return map[session.state] ?? { label: 'État inconnu', color: 'neutral' }
}
