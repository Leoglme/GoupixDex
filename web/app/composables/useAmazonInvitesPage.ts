import type { ComputedRef, Ref } from 'vue'
import { isAxiosError } from 'axios'
import type {
  AmazonAccountConnectionState,
  AmazonInvite,
  AmazonInviteStatusCounts,
  AmazonInvitesFetchParams,
  AmazonSessionResponse,
  AmazonStatusFilter,
  AmazonStatusSelectItem,
  AmazonVerifyAllAccountsResponse,
} from '~/types/amazonInvites'
import type { AmazonWorkerProgressPayload } from '~/types/amazonWorkerProgress'
import {
  loadAmazonInvitesPrefs,
  loadInvitesCacheByAccount,
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
 * Coupe une liste d’invitations à la limite « produits max » de la page.
 *
 * @param list - Lignes à tronquer.
 * @param maxItems - Limite saisie dans la barre d’outils.
 * @returns {AmazonInvite[]} Les `maxItems` premières lignes.
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
 * Page Invitations Amazon : catalogue partagé, un statut par compte du coffre, demandes depuis le compte affiché.
 *
 * @returns Reactive state, `displayItems`, `load`, `refresh`, `requestProductInvite`, `switchActiveAccount`.
 */
export function useAmazonInvitesPage() {
  const { fetchSession, fetchInvites, refreshInvites, verifyAllAccounts, requestInvite } = useAmazonWorker()
  const { fetchOverview, setActiveAccount } = useAmazonAccounts()
  const toast = useToast()

  const loading: Ref<boolean> = ref(false)
  const refreshing: Ref<boolean> = ref(false)
  const error: Ref<string | null> = ref(null)
  const session: Ref<AmazonSessionResponse | null> = ref(null)
  /** Lignes de la dernière recherche Amazon, communes à tous les comptes. */
  const catalog: Ref<AmazonInvite[]> = ref([])
  const rowsByAccount: Ref<Record<string, AmazonInvite[]>> = ref({})
  const accountConnectionStates: Ref<Record<string, AmazonAccountConnectionState>> = ref({})
  const refreshedAt: Ref<string | null> = ref(null)
  /** Filtre local + requête Amazon lors d’« Actualiser » (vide = défaut worker). */
  const searchQuery: Ref<string> = ref('')
  const maxItems: Ref<number> = ref(DEFAULT_AMAZON_INVITES_MAX_ITEMS)
  const statusFilter: Ref<AmazonStatusFilter> = ref('all')
  /** Live log lines during `refresh()` (WebSocket `/ws/progress`). */
  const refreshLogLines: Ref<string[]> = ref([])
  /** Latest worker message for the progress subtitle. */
  const refreshPhaseHint: Ref<string> = ref('')
  /** Invites received over WebSocket during ``refresh()`` for the displayed account, shown before the calls complete. */
  const streamingInvites: Ref<AmazonInvite[]> = ref([])
  /** ASIN whose invite request is in flight (worker ``POST /amazon/invites/request``). */
  const requestInviteLoadingAsin: Ref<string | null> = ref(null)
  const selectedAccountId: Ref<number | undefined> = ref(undefined)
  /** Last account id confirmed by API + worker (avoids duplicate switch toasts). */
  const confirmedActiveAccountId: Ref<number | undefined> = ref(undefined)
  const vaultAccounts: Ref<{ id: number; label: string | null; amazon_email: string }[]> = ref([])

  const accountSelectItems = computed(() =>
    vaultAccounts.value.map((a) => ({
      label: a.label ? `${a.label} (${a.amazon_email})` : a.amazon_email,
      value: a.id,
    })),
  )

  const vaultAccountCount = computed(() => vaultAccounts.value.length)

  const catalogAsUnverified: ComputedRef<AmazonInvite[]> = computed(() =>
    catalog.value.map((row) => ({ ...row, status: 'listing_only' })),
  )

  /** Lignes du compte affiché ; à défaut, le catalogue non vérifié (ou tel quel sans compte du coffre). */
  const items: ComputedRef<AmazonInvite[]> = computed(() => {
    const id = selectedAccountId.value
    if (id == null) {
      return catalog.value
    }
    return rowsByAccount.value[String(id)] ?? catalogAsUnverified.value
  })

  /**
   * Enregistre les lignes vérifiées d’un compte (mémoire + cache local).
   *
   * @param accountId - Compte du coffre.
   * @param rows - Lignes avec statut pour ce compte.
   * @param at - Horodatage ISO de la vérification.
   * @returns {void} Cette fonction ne retourne rien.
   */
  function setAccountRows(accountId: number, rows: AmazonInvite[], at: string | null): void {
    const trimmed = trimInvitesToMaxItems(rows, maxItems.value)
    rowsByAccount.value = { ...rowsByAccount.value, [String(accountId)]: trimmed }
    if (import.meta.client && trimmed.length) {
      saveInvitesCacheForAccount(accountId, trimmed, at)
    }
  }

  /**
   * Upsert one invite into ``streamingInvites`` keyed by ASIN or id.
   *
   * @param inv - Ligne reçue en temps réel.
   * @returns {void} Cette fonction ne retourne rien.
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
   * Merge ``invite_preview`` from a WebSocket progress payload into ``streamingInvites``,
   * only when it concerns the displayed account (no account = search phase on the active one).
   *
   * @param payload - Message du flux `/ws/progress`.
   * @returns {void} Cette fonction ne retourne rien.
   */
  function mergeInvitePreviewFromWs(payload: AmazonWorkerProgressPayload): void {
    const raw = payload.invite_preview
    if (!raw || typeof raw !== 'object') {
      return
    }
    if (payload.account_id != null && payload.account_id !== selectedAccountId.value) {
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
      // Dernier catalogue + statuts par compte : la page n’est pas vide en attendant le worker.
      if (p?.cachedInvites?.length) {
        catalog.value = p.cachedInvites
        refreshedAt.value = p.cachedRefreshedAt ?? null
      }
      const byAccount = loadInvitesCacheByAccount()
      const restored: Record<string, AmazonInvite[]> = {}
      for (const [id, cache] of Object.entries(byAccount)) {
        restored[id] = trimInvitesToMaxItems(cache.items, maxItems.value)
      }
      rowsByAccount.value = restored
      if (p?.accountConnectionStates) {
        accountConnectionStates.value = p.accountConnectionStates
      }
    }
  })

  /**
   * Persist the shared catalog so the page is not empty on the next visit.
   *
   * @returns {void} Cette fonction ne retourne rien.
   */
  function saveCatalogCache(): void {
    if (import.meta.client) {
      saveAmazonInvitesPrefs({ cachedInvites: catalog.value, cachedRefreshedAt: refreshedAt.value })
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
   * Charge les comptes du coffre et le compte actif côté API.
   *
   * @returns {Promise<void>} Résolu quand `vaultAccounts` et le compte sélectionné sont à jour.
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
   * Change le compte affiché immédiatement (statuts déjà en mémoire) et prévient l’API en arrière-plan.
   *
   * @param accountId - Compte du coffre à afficher.
   * @returns {Promise<void>} Résolu quand l’API a enregistré le compte actif (ou après le retour arrière en cas d’échec).
   */
  async function switchActiveAccount(accountId: number): Promise<void> {
    if (accountId === confirmedActiveAccountId.value) {
      selectedAccountId.value = accountId
      return
    }
    if (refreshing.value) {
      selectedAccountId.value = confirmedActiveAccountId.value
      return
    }

    const previousConfirmed = confirmedActiveAccountId.value
    selectedAccountId.value = accountId
    confirmedActiveAccountId.value = accountId
    error.value = null

    try {
      const overview = await setActiveAccount(accountId)
      vaultAccounts.value = overview.accounts
      const active = overview.active_account_id ?? undefined
      if (active == null || active !== accountId) {
        throw new Error('Compte actif non enregistré.')
      }
    } catch (e: unknown) {
      selectedAccountId.value = previousConfirmed
      confirmedActiveAccountId.value = previousConfirmed
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
    }
  }

  /**
   * Charge la session worker et les lignes en cache du compte actif (sans nouvelle recherche Amazon).
   *
   * @returns {Promise<void>} Resolves after state is updated or `error` is set.
   */
  async function load(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      await loadVaultAccounts()
      const params = fetchParams.value
      const [s, inv] = await Promise.all([fetchSession(), fetchInvites(params)])
      session.value = s
      const aid = confirmedActiveAccountId.value
      // A restarted worker answers with an empty cache: keep the locally cached rows in that case.
      if (inv.items.length && aid != null) {
        setAccountRows(aid, inv.items, inv.refreshed_at ?? null)
        if (!catalog.value.length) {
          catalog.value = trimInvitesToMaxItems(inv.items, maxItems.value)
          refreshedAt.value = inv.refreshed_at ?? null
          saveCatalogCache()
        }
      }
    } catch (e: unknown) {
      error.value = errorMessageFromUnknown(e, 'Impossible de charger vos invitations pour le moment.')
    } finally {
      loading.value = false
    }
  }

  /**
   * Applique le résultat de la vérification multi-comptes et prévient si un compte n’a pas pu être vérifié.
   *
   * @param res - Réponse de ``POST /amazon/invites/verify-all``.
   * @returns {void} Cette fonction ne retourne rien.
   */
  function applyVerifyAllResult(res: AmazonVerifyAllAccountsResponse): void {
    for (const [id, rows] of Object.entries(res.rows_by_account)) {
      const accountId = Number(id)
      if (Number.isFinite(accountId)) {
        setAccountRows(accountId, rows, res.refreshed_at)
      }
    }
    if (res.refreshed_at) {
      refreshedAt.value = res.refreshed_at
    }
    accountConnectionStates.value = res.account_states ?? {}
    if (import.meta.client) {
      saveAmazonInvitesPrefs({ accountConnectionStates: accountConnectionStates.value })
    }
    const failed = Object.keys(res.errors ?? {})
    if (failed.length) {
      const labels = failed.map((id) => {
        const acc = vaultAccounts.value.find((a) => String(a.id) === id)
        return acc ? (acc.label ?? acc.amazon_email) : `compte ${id}`
      })
      toast.add({
        title: 'Comptes non connectés',
        description: `Connexion impossible sur : ${labels.join(', ')}. Vérifiez leurs identifiants dans le coffre.`,
        color: 'warning',
      })
    }
  }

  /**
   * « Actualiser » : recherche sur le compte actif, puis vérification du même catalogue sur chaque
   * compte du coffre. Ouvre `/ws/progress` quand c’est possible pour afficher les logs en direct.
   *
   * @returns {Promise<void>} Resolves after refresh completes or fails into `error`.
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
      // Avec des comptes en coffre, la recherche ne vérifie rien : chaque compte est vérifié dans Chrome juste après.
      const hasVaultAccounts = vaultAccounts.value.length > 0
      const res = await refreshInvites(fetchParams.value, !hasVaultAccounts)
      catalog.value = trimInvitesToMaxItems(res.items, maxItems.value)
      if (res.refreshed_at) {
        refreshedAt.value = res.refreshed_at
      }
      saveCatalogCache()
      if (res.message && !refreshPhaseHint.value) {
        refreshPhaseHint.value = res.message
      }

      if (catalog.value.length && hasVaultAccounts) {
        streamingInvites.value = []
        const all = await verifyAllAccounts(catalog.value)
        applyVerifyAllResult(all)
        if (all.message) {
          refreshPhaseHint.value = all.message
        }
      }
      streamingInvites.value = []
      session.value = await fetchSession()
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
   * @returns {AmazonInvite[]} Filtered list.
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
   * Envoie la demande d’invitation depuis le compte affiché (le worker utilise ses cookies), puis met à jour sa ligne.
   *
   * @param invite - Ligne dont on demande l’invitation.
   * @returns {Promise<void>} Résolu après le toast de résultat.
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
    const accountId = selectedAccountId.value
    if (accountId == null) {
      toast.add({
        title: 'Aucun compte sélectionné',
        description: 'Choisissez le compte Amazon depuis lequel envoyer la demande.',
        color: 'error',
      })
      return
    }
    requestInviteLoadingAsin.value = asin.toUpperCase()
    try {
      const res = await requestInvite(asin, accountId)
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
        const current = rowsByAccount.value[String(accountId)] ?? catalogAsUnverified.value
        setAccountRows(
          accountId,
          current.map((row) => ((row.asin ?? '').trim().toUpperCase() === key ? updated : row)),
          refreshedAt.value,
        )
        streamingInvites.value = streamingInvites.value.map((row) =>
          (row.asin ?? '').trim().toUpperCase() === key ? updated : row,
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
    accountConnectionStates,
    selectedAccountId,
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
