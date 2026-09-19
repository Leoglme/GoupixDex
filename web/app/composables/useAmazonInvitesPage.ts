import type { ComputedRef, Ref } from 'vue'
import { isAxiosError } from 'axios'
import type {
  AmazonInvite,
  AmazonInviteStatusCounts,
  AmazonInvitesFetchParams,
  AmazonSessionResponse,
  AmazonStatusFilter,
  AmazonStatusSelectItem,
} from '~/types/amazonInvites'
import type { AmazonWorkerProgressPayload } from '~/types/amazonWorkerProgress'
import {
  loadAmazonInvitesPrefs,
  loadInvitesCacheForAccount,
  saveAmazonInvitesPrefs,
  saveInvitesCacheForAccount,
} from '~/composables/useAmazonInvitesPersistence'
import { buildAmazonProgressWebSocketUrl, useAmazonWorker } from '~/composables/useAmazonWorker'
import { formatAmazonWorkerProgressLine } from '~/utils/amazonWorkerProgressFormat'
import { openAmazonProgressWebSocket } from '~/utils/amazonProgressWebSocket'
import {
  clampMaxItems,
  DEFAULT_AMAZON_INVITES_MAX_ITEMS,
  legacyMaxPagesToMaxItems,
  maxItemsToScanPages,
} from '~/utils/amazonInvitesScanLimit'

/**
 *
 */
function trimInvitesToMaxItems(list: AmazonInvite[], maxItems: number): AmazonInvite[] {
  return list.slice(0, clampMaxItems(maxItems))
}

/**
 * Map Axios / network failures to short user-visible copy for the invites UI.
 *
 * @param e - Thrown rejection from `fetch*` calls.
 * @param fallback - Generic message when status-specific text does not apply.
 * @returns {string} User-visible error line.
 */
function withTimeout<T>(promise: Promise<T>, ms: number, label: string): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`${label} (délai dépassé).`)), ms)
    promise.then(
      (v) => {
        clearTimeout(timer)
        resolve(v)
      },
      (e: unknown) => {
        clearTimeout(timer)
        reject(e)
      },
    )
  })
}

/**
 *
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
  }
  return fallback
}

/**
 * Amazon Invites page: worker session + invites list, persisted filters, client-side search.
 *
 * @returns Reactive state, `displayItems`, `load`, and `refresh`.
 */
export function useAmazonInvitesPage() {
  const { fetchSession, fetchInvites, refreshInvites, reverifyInvites, requestInvite, activateVaultAccount } =
    useAmazonWorker()
  const { fetchOverview, setActiveAccount } = useAmazonAccounts()
  const toast = useToast()

  const loading: Ref<boolean> = ref(false)
  const refreshing: Ref<boolean> = ref(false)
  const error: Ref<string | null> = ref(null)
  const session: Ref<AmazonSessionResponse | null> = ref(null)
  const items: Ref<AmazonInvite[]> = ref([])
  const refreshedAt: Ref<string | null> = ref(null)
  /** Filtre local + requête Amazon lors d’« Actualiser » (vide = défaut worker). */
  const searchQuery: Ref<string> = ref('')
  const maxItems: Ref<number> = ref(DEFAULT_AMAZON_INVITES_MAX_ITEMS)
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
  const selectedAccountId: Ref<number | undefined> = ref(undefined)
  /** Last account id confirmed by API + worker (avoids duplicate switch toasts). */
  const confirmedActiveAccountId: Ref<number | undefined> = ref(undefined)
  /** True only while the API active account is being saved (should stay brief). */
  const accountSwitching: Ref<boolean> = ref(false)
  /** Chrome profile bind / optional reverify after an instant account swap. */
  const accountBackgroundSync: Ref<boolean> = ref(false)
  const vaultAccounts: Ref<{ id: number; label: string | null; amazon_email: string }[]> = ref([])

  const accountSelectItems = computed(() =>
    vaultAccounts.value.map((a) => ({
      label: a.label ? `${a.label} (${a.amazon_email})` : a.amazon_email,
      value: a.id,
    })),
  )

  const vaultAccountCount = computed(() => vaultAccounts.value.length)

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
    streamingInvites.value = trimInvitesToMaxItems(next, maxItems.value)
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
    q: searchQuery.value,
    max_pages: maxItemsToScanPages(maxItems.value, Boolean(searchQuery.value.trim())),
    max_items: clampMaxItems(maxItems.value),
  }))

  onMounted((): void => {
    if (import.meta.client) {
      const p = loadAmazonInvitesPrefs()
      if (p?.searchQuery != null) {
        searchQuery.value = p.searchQuery
      } else if (p?.optionalSearch != null) {
        searchQuery.value = p.optionalSearch
      }
      if (p?.maxItems != null) {
        maxItems.value = clampMaxItems(p.maxItems)
      } else if (p?.maxPages != null) {
        maxItems.value = legacyMaxPagesToMaxItems(p.maxPages)
      }
      if (p?.statusFilter != null) {
        statusFilter.value = migratePersistedStatusFilter(p.statusFilter)
      }
      // Show the last fetched list immediately; `load()` replaces it when the worker answers.
      if (p?.cachedInvites?.length && !items.value.length) {
        items.value = p.cachedInvites
        refreshedAt.value = p.cachedRefreshedAt ?? null
      }
    }
  })

  /**
   * Persist the current invite list so the page is not empty on the next visit.
   */
  function saveInvitesCache(): void {
    if (import.meta.client) {
      saveAmazonInvitesPrefs({ cachedInvites: items.value, cachedRefreshedAt: refreshedAt.value })
      const aid = confirmedActiveAccountId.value
      if (aid != null && items.value.length) {
        saveInvitesCacheForAccount(aid, items.value, refreshedAt.value)
      }
    }
  }

  watch([searchQuery, maxItems, statusFilter], (): void => {
    if (import.meta.client) {
      saveAmazonInvitesPrefs({
        searchQuery: searchQuery.value,
        maxItems: clampMaxItems(maxItems.value),
        statusFilter: statusFilter.value,
      })
    }
  })

  /**
   * Parallel fetch of session + invites (`fetchInvites` with current `fetchParams`).
   *
   * @returns Resolves after state is updated or `error` is set.
   */
  async function loadVaultAccounts(): Promise<void> {
    try {
      const overview = await fetchOverview()
      vaultAccounts.value = overview.accounts
      const active = overview.active_account_id ?? undefined
      selectedAccountId.value = active
      confirmedActiveAccountId.value = active
    } catch {
      vaultAccounts.value = []
    }
  }

  /**
   *
   */
  async function syncWorkerAfterAccountSwitch(
    accountId: number,
    catalogForReverify: AmazonInvite[],
    hadLocalCache: boolean,
  ): Promise<void> {
    accountBackgroundSync.value = true
    try {
      await withTimeout(activateVaultAccount(accountId), 620_000, 'Connexion au compte Amazon')
      try {
        session.value = await fetchSession()
      } catch {
        /* ignore */
      }

      const inv = await fetchInvites(fetchParams.value)
      if (inv.items.length) {
        items.value = trimInvitesToMaxItems(inv.items, maxItems.value)
        refreshedAt.value = inv.refreshed_at ?? null
        saveInvitesCache()
        return
      }

      if (hadLocalCache || !catalogForReverify.length) {
        return
      }

      const res = await withTimeout(reverifyInvites(catalogForReverify), 120_000, 'Mise à jour des statuts')
      items.value = trimInvitesToMaxItems(res.items, maxItems.value)
      if (res.refreshed_at) {
        refreshedAt.value = res.refreshed_at
      }
      saveInvitesCache()
    } catch {
      /* liste déjà affichée depuis le cache compte */
    } finally {
      accountBackgroundSync.value = false
    }
  }

  /**
   *
   */
  async function switchActiveAccount(accountId: number): Promise<void> {
    if (accountId === confirmedActiveAccountId.value) {
      selectedAccountId.value = accountId
      return
    }
    if (accountSwitching.value || refreshing.value) {
      selectedAccountId.value = confirmedActiveAccountId.value
      return
    }

    const previousConfirmed = confirmedActiveAccountId.value
    const previousItems = [...items.value]
    const previousRefreshedAt = refreshedAt.value
    const catalogForReverify = items.value.length ? [...items.value] : []

    if (previousConfirmed != null && items.value.length) {
      saveInvitesCacheForAccount(previousConfirmed, items.value, refreshedAt.value)
    }

    const localHit = loadInvitesCacheForAccount(accountId)
    const hadLocalCache = Boolean(localHit?.items.length)
    if (localHit?.items.length) {
      items.value = trimInvitesToMaxItems(localHit.items, maxItems.value)
      refreshedAt.value = localHit.refreshedAt ?? null
    }

    selectedAccountId.value = accountId
    accountSwitching.value = true
    error.value = null

    try {
      const overview = await setActiveAccount(accountId)
      vaultAccounts.value = overview.accounts
      const active = overview.active_account_id ?? undefined
      if (active == null || active !== accountId) {
        throw new Error('Compte actif non enregistré.')
      }
      confirmedActiveAccountId.value = active
      selectedAccountId.value = active
    } catch (e: unknown) {
      selectedAccountId.value = previousConfirmed
      confirmedActiveAccountId.value = previousConfirmed
      items.value = previousItems
      refreshedAt.value = previousRefreshedAt
      try {
        await loadVaultAccounts()
      } catch {
        /* ignore */
      }
      toast.add({
        title: 'Changement de compte impossible',
        description: errorMessageFromUnknown(e, 'Réessayez.'),
        color: 'error',
      })
      accountSwitching.value = false
      return
    } finally {
      accountSwitching.value = false
    }

    void syncWorkerAfterAccountSwitch(accountId, catalogForReverify, hadLocalCache)
  }

  /**
   *
   */
  async function load(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      await loadVaultAccounts()
      const aid = confirmedActiveAccountId.value
      if (aid != null) {
        const hit = loadInvitesCacheForAccount(aid)
        if (hit?.items.length) {
          items.value = trimInvitesToMaxItems(hit.items, maxItems.value)
          refreshedAt.value = hit.refreshedAt ?? null
        }
      }
      const params = fetchParams.value
      const [s, inv] = await Promise.all([fetchSession(), fetchInvites(params)])
      session.value = s
      // A restarted worker answers with an empty cache: keep the locally cached list in that case.
      if (inv.items.length || !items.value.length) {
        items.value = trimInvitesToMaxItems(inv.items, maxItems.value)
        refreshedAt.value = inv.refreshed_at ?? null
        saveInvitesCache()
      }
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

    const wsTarget = buildAmazonProgressWebSocketUrl()
    let ws: WebSocket | null = null
    if (wsTarget) {
      ws = await openAmazonProgressWebSocket(
        wsTarget.url,
        (payload: AmazonWorkerProgressPayload) => {
          if (payload.message) {
            refreshPhaseHint.value = payload.message
          }
          mergeInvitePreviewFromWs(payload)
          refreshLogLines.value = [...refreshLogLines.value, formatAmazonWorkerProgressLine(payload)].slice(-120)
        },
        5000,
        wsTarget.protocols,
      )
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
      items.value = trimInvitesToMaxItems(res.items, maxItems.value)
      streamingInvites.value = []
      if (res.refreshed_at) {
        refreshedAt.value = res.refreshed_at
      }
      saveInvitesCache()
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
   * Applies status + local search filters (same as ``displayItems``).
   *
   * @param list - List to filter (main cache or real-time stream).
   * @returns Filtered list.
   */
  function filterInvitesClientSide(list: AmazonInvite[]): AmazonInvite[] {
    const sf = statusFilter.value
    if (sf === 'all') {
      return list
    }
    return list.filter((i) => i.status === sf)
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
      const updated = res.invite
      if (updated) {
        const key = asin.toUpperCase()
        items.value = items.value.map((row) => ((row.asin ?? '').trim().toUpperCase() === key ? updated : row))
        streamingInvites.value = streamingInvites.value.map((row) =>
          (row.asin ?? '').trim().toUpperCase() === key ? updated : row,
        )
        saveInvitesCache()
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
    maxItems,
    statusFilter,
    statusSelectItems,
    displayItems,
    streamingInvites,
    streamingDisplayItems,
    refreshLogLines,
    refreshPhaseHint,
    requestInviteLoadingAsin,
    accountSelectItems,
    vaultAccountCount,
    selectedAccountId,
    accountSwitching,
    accountBackgroundSync,
    load,
    refresh,
    requestProductInvite,
    switchActiveAccount,
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
