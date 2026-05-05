import type { ComputedRef, Ref } from 'vue'
import { isAxiosError } from 'axios'
import { normalizeSearchQuery } from '~/utils/searchNormalize'
import type {
  AmazonInvite,
  AmazonInviteStatusCounts,
  AmazonInvitesFetchParams,
  AmazonSessionResponse,
  AmazonStatusFilter,
  AmazonStatusSelectItem,
} from '~/types/amazonInvites'
import type { AmazonWorkerProgressPayload } from '~/types/amazonWorkerProgress'
import { loadAmazonInvitesPrefs, saveAmazonInvitesPrefs } from '~/composables/useAmazonInvitesPersistence'
import { buildAmazonProgressWebSocketUrl, useAmazonWorker } from '~/composables/useAmazonWorker'
import { formatAmazonWorkerProgressLine } from '~/utils/amazonWorkerProgressFormat'
import { openAmazonProgressWebSocket } from '~/utils/amazonProgressWebSocket'

/**
 * Clamp worker page depth to a sane `[1, 50]` integer (defaults when NaN).
 *
 * @param n - Raw UI value from `maxPages`.
 * @returns {number} Clamped page count.
 */
function clampMaxPages(n: number): number {
  if (!Number.isFinite(n)) {
    return 2
  }
  return Math.min(50, Math.max(1, Math.round(n)))
}

/**
 * Map Axios / network failures to short user-visible copy for the invites UI.
 *
 * @param e - Thrown rejection from `fetch*` calls.
 * @param fallback - Generic message when status-specific text does not apply.
 * @returns {string} User-visible error line.
 */
function errorMessageFromUnknown(e: unknown, fallback: string): string {
  if (isAxiosError(e)) {
    const status = e.response?.status
    if (status === 401) {
      return 'Votre session GoupixDex a expiré. Déconnectez-vous puis reconnectez-vous.'
    }
    if (status === 403) {
      return 'Accès refusé. Vérifiez que votre compte est toujours autorisé.'
    }
    if (e.message === 'Network Error' || e.code === 'ERR_NETWORK') {
      return 'Connexion impossible. Vérifiez internet, réessayez dans un instant, ou ouvrez GoupixDex sur ordinateur si vous utilisez l’application bureau.'
    }
    if (status != null && status >= 500) {
      return 'Le service est temporairement indisponible. Réessayez dans quelques minutes.'
    }
    return fallback
  }
  if (e instanceof Error && e.message && !e.message.includes('Network')) {
    return fallback
  }
  return fallback
}

/**
 * Amazon Invites page: worker session + invites list, persisted filters, client-side search.
 *
 * @returns Reactive state, `displayItems`, `load`, and `refresh`.
 */
export function useAmazonInvitesPage() {
  const { fetchSession, fetchInvites, refreshInvites, requestInvite } = useAmazonWorker()
  const toast = useToast()

  const loading: Ref<boolean> = ref(false)
  const refreshing: Ref<boolean> = ref(false)
  const error: Ref<string | null> = ref(null)
  const session: Ref<AmazonSessionResponse | null> = ref(null)
  const items: Ref<AmazonInvite[]> = ref([])
  const refreshedAt: Ref<string | null> = ref(null)
  /** Filter on the loaded results */
  const searchQuery: Ref<string> = ref('')
  const hideExpired: Ref<boolean> = ref(false)
  /** Optional search query sent to the worker */
  const optionalSearch: Ref<string> = ref('')
  const maxPages: Ref<number> = ref(2)
  const statusFilter: Ref<AmazonStatusFilter> = ref('all')
  /** Live log lines during `refresh()` (WebSocket `/ws/progress`). */
  const refreshLogLines: Ref<string[]> = ref([])
  /** Latest worker message for the progress subtitle. */
  const refreshPhaseHint: Ref<string> = ref('')
  /**
   * Invites received over WebSocket during ``refresh()`` (search + verification), shown before
   * ``POST /amazon/invites/refresh`` completes.
   */
  const streamingInvites: Ref<AmazonInvite[]> = ref([])
  /** ASIN whose invite request is in flight (worker ``POST /amazon/invites/request``). */
  const requestInviteLoadingAsin: Ref<string | null> = ref(null)

  /**
   * Upsert one invite into ``streamingInvites`` keyed by ASIN or id.
   */
  function mergeStreamInvite(inv: AmazonInvite): void {
    const key = ((inv.asin ?? inv.id) || '').trim().toUpperCase()
    if (!key) {
      return
    }
    const next = [...streamingInvites.value]
    const ix = next.findIndex((r) => ((r.asin ?? r.id) || '').trim().toUpperCase() === key)
    if (ix >= 0) {
      next[ix] = inv
    } else {
      next.push(inv)
    }
    streamingInvites.value = next
  }

  /**
   * Merge ``invite_preview`` from a WebSocket progress payload into ``streamingInvites``.
   */
  function mergeInvitePreviewFromWs(payload: AmazonWorkerProgressPayload): void {
    const raw = payload.invite_preview
    if (!raw || typeof raw !== 'object') {
      return
    }
    const inv = raw as AmazonInvite
    if (!inv.id || !inv.title || typeof inv.status !== 'string') {
      return
    }
    mergeStreamInvite(inv)
  }

  const fetchParams: ComputedRef<AmazonInvitesFetchParams> = computed(() => ({
    q: optionalSearch.value,
    max_pages: clampMaxPages(maxPages.value),
  }))

  onMounted((): void => {
    if (import.meta.client) {
      const p = loadAmazonInvitesPrefs()
      if (p?.searchQuery != null) {
        searchQuery.value = p.searchQuery
      }
      if (p?.hideExpired != null) {
        hideExpired.value = p.hideExpired
      }
      if (p?.optionalSearch != null) {
        optionalSearch.value = p.optionalSearch
      }
      if (p?.maxPages != null) {
        maxPages.value = clampMaxPages(p.maxPages)
      }
      if (p?.statusFilter != null) {
        statusFilter.value = migratePersistedStatusFilter(p.statusFilter)
      }
    }
  })

  watch([searchQuery, hideExpired, optionalSearch, maxPages, statusFilter], (): void => {
    if (import.meta.client) {
      saveAmazonInvitesPrefs({
        searchQuery: searchQuery.value,
        hideExpired: hideExpired.value,
        optionalSearch: optionalSearch.value,
        maxPages: clampMaxPages(maxPages.value),
        statusFilter: statusFilter.value,
      })
    }
  })

  /**
   * Parallel fetch of session + invites (`fetchInvites` with current `fetchParams`).
   *
   * @returns Resolves after state is updated or `error` is set.
   */
  async function load(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const params = fetchParams.value
      const [s, inv] = await Promise.all([fetchSession(), fetchInvites(params)])
      session.value = s
      items.value = inv.items
      refreshedAt.value = inv.refreshed_at ?? null
    } catch (e: unknown) {
      error.value = errorMessageFromUnknown(e, 'Impossible de charger vos invitations pour le moment.')
    } finally {
      loading.value = false
    }
  }

  /**
   * Force worker rescrape (`refreshInvites`) then reload session snapshot.
   * Opens `/ws/progress` when possible so the UI can show live scrape logs.
   *
   * @returns Resolves after refresh completes or fails into `error`.
   */
  async function refresh(): Promise<void> {
    refreshing.value = true
    error.value = null
    refreshLogLines.value = []
    refreshPhaseHint.value = ''
    streamingInvites.value = []

    const wsUrl = buildAmazonProgressWebSocketUrl()
    let ws: WebSocket | null = null
    if (wsUrl) {
      ws = await openAmazonProgressWebSocket(wsUrl, (payload: AmazonWorkerProgressPayload) => {
        if (payload.message) {
          refreshPhaseHint.value = payload.message
        }
        mergeInvitePreviewFromWs(payload)
        refreshLogLines.value = [...refreshLogLines.value, formatAmazonWorkerProgressLine(payload)].slice(-120)
      })
      if (!ws) {
        refreshLogLines.value = [
          '[info] Connexion au flux temps réel impossible — la recherche continue (logs détaillés indisponibles).',
        ]
      }
    } else {
      refreshLogLines.value = [
        '[info] Flux temps réel non disponible (session ou URL du worker manquante). La recherche continue.',
      ]
    }

    try {
      const params = fetchParams.value
      const res = await refreshInvites(params)
      items.value = res.items
      streamingInvites.value = []
      if (res.refreshed_at) {
        refreshedAt.value = res.refreshed_at
      }
      session.value = await fetchSession()
      if (res.message && !refreshPhaseHint.value) {
        refreshPhaseHint.value = res.message
      }
    } catch (e: unknown) {
      error.value = errorMessageFromUnknown(e, 'Impossible de mettre à jour la liste. Réessayez.')
      streamingInvites.value = []
    } finally {
      try {
        ws?.close()
      } catch {
        /* ignore */
      }
      refreshing.value = false
    }
  }

  const statusCounts: ComputedRef<AmazonInviteStatusCounts> = computed(() => {
    const r = items.value
    return {
      all: r.length,
      accepted: r.filter((i) => i.status === 'accepted').length,
      requested: r.filter((i) => i.status === 'requested').length,
      not_requested: r.filter((i) => i.status === 'not_requested').length,
    }
  })

  const statusSelectItems: ComputedRef<AmazonStatusSelectItem[]> = computed(() => {
    const c = statusCounts.value
    return [
      { label: `Tous les statuts (${c.all})`, value: 'all' },
      { label: `Commandable (${c.accepted})`, value: 'accepted' },
      { label: `Invitation demandée (${c.requested})`, value: 'requested' },
      { label: `Non demandée (${c.not_requested})`, value: 'not_requested' },
    ]
  })

  /**
   * Applies status / “hide expired” / local search filters (same as ``displayItems``).
   *
   * @param list - List to filter (main cache or real-time stream).
   * @returns Filtered list.
   */
  function filterInvitesClientSide(list: AmazonInvite[]): AmazonInvite[] {
    let out = list
    const sf = statusFilter.value
    if (sf !== 'all') {
      out = out.filter((i) => i.status === sf)
    }
    if (hideExpired.value) {
      out = out.filter((i) => i.status !== 'expired')
    }
    const q = normalizeSearchQuery(searchQuery.value)
    if (!q) {
      return out
    }
    return out.filter((i) => {
      const hay = normalizeSearchQuery(`${i.title} ${i.asin ?? ''}`)
      return hay.includes(q)
    })
  }

  const displayItems: ComputedRef<AmazonInvite[]> = computed(() => filterInvitesClientSide(items.value))

  /** Same filters as ``displayItems``, applied to the real-time stream during ``refresh()``. */
  const streamingDisplayItems: ComputedRef<AmazonInvite[]> = computed(() =>
    filterInvitesClientSide(streamingInvites.value),
  )

  /**
   * Sends the invite request via the worker (POST Amazon), then updates the local row.
   */
  async function requestProductInvite(invite: AmazonInvite): Promise<void> {
    const asin = invite.asin?.trim()
    if (!asin) {
      toast.add({
        title: 'ASIN manquant',
        description: 'Impossible d’envoyer la demande pour cette fiche.',
        color: 'error',
      })
      return
    }
    requestInviteLoadingAsin.value = asin.toUpperCase()
    try {
      const res = await requestInvite(asin)
      if (!res.success) {
        toast.add({
          title: 'Demande non envoyée',
          description: res.message,
          color: 'warning',
        })
        return
      }
      if (res.invite) {
        const key = asin.toUpperCase()
        items.value = items.value.map((row) => ((row.asin ?? '').trim().toUpperCase() === key ? res.invite! : row))
        streamingInvites.value = streamingInvites.value.map((row) =>
          (row.asin ?? '').trim().toUpperCase() === key ? res.invite! : row,
        )
      }
      toast.add({
        title: 'Invitation demandée',
        description: res.message,
        color: 'success',
      })
    } catch (e: unknown) {
      toast.add({
        title: 'Erreur',
        description: errorMessageFromUnknown(e, 'Le worker n’a pas pu traiter la demande.'),
        color: 'error',
      })
    } finally {
      requestInviteLoadingAsin.value = null
    }
  }

  return {
    loading,
    refreshing,
    error,
    session,
    items,
    refreshedAt,
    searchQuery,
    hideExpired,
    optionalSearch,
    maxPages,
    statusFilter,
    statusSelectItems,
    displayItems,
    streamingInvites,
    streamingDisplayItems,
    refreshLogLines,
    refreshPhaseHint,
    requestInviteLoadingAsin,
    load,
    refresh,
    requestProductInvite,
  }
}

/**
 * Type guard for persisted `statusFilter` values.
 *
 * @param v - Value read from storage.
 * @returns Whether `v` is a valid {@link AmazonStatusFilter}.
 */
export function isValidAmazonStatusFilter(v: unknown): v is AmazonStatusFilter {
  return v === 'all' || v === 'accepted' || v === 'requested' || v === 'not_requested'
}

/**
 * Map legacy persisted filters (`pending`, etc.) to the current filter model.
 *
 * @param v - Raw value from storage.
 * @returns A valid {@link AmazonStatusFilter} (defaults to `all`).
 */
export function migratePersistedStatusFilter(v: unknown): AmazonStatusFilter {
  if (isValidAmazonStatusFilter(v)) {
    return v
  }
  return 'all'
}
