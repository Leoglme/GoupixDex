import type { Ref } from 'vue'
import type { AxiosInstance } from 'axios'

export type EbaySoldTopCategory = 'cards' | 'graded' | 'sealed'
export type EbaySoldTopStatus = 'idle' | 'pending' | 'running' | 'completed' | 'failed'

export interface EbaySoldTopRow {
  rank: number
  category: EbaySoldTopCategory
  fingerprint: string
  grade: string | null
  display_title: string
  image_url: string | null
  sample_listing_url: string | null
  count: number
  total_value_eur: number
  median_price_eur: number | null
  min_price_eur: number | null
  max_price_eur: number | null
  approx_hours_min: number | null
}

/** Raw sold listing — same shape as ``EbaySoldScrapeRow``. */
export interface EbaySoldTopItem {
  title: string
  price_eur: number | null
  listing_url: string
  image_url: string | null
  item_id: string | null
  sold_caption: string | null
  approx_hours_ago: number | null
}

export interface EbaySoldTopResultBody {
  query: string
  window_hours: number
  pages_requested: number
  total_observed: number
  /** All in-window listings, recency-ordered. Drives the List view. */
  items: EbaySoldTopItem[]
  cards: EbaySoldTopRow[]
  graded: EbaySoldTopRow[]
  sealed: EbaySoldTopRow[]
  groups_count: { cards: number; graded: number; sealed: number }
  source: string
}

interface JobEnvelope {
  job_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  query: string
  window_hours: number
  language: string | null
  pages_requested: number
  pages_done: number
  total_observed: number
  partial_items: EbaySoldTopItem[]
  result: EbaySoldTopResultBody | null
  error: string | null
  created_at: number
  updated_at: number
  started_at: number | null
  completed_at: number | null
  ebay_sold_search_url: string
  cached?: boolean
}

export interface EbaySoldTopInput {
  q: string
  windowHours: number
  pages?: number
  scrapeLimit?: number
  topLimit?: number
  minCount?: number
  /** Optional eBay `Langue` aspect filter (`fr` | `ja` | `null`). */
  language?: string | null
}

const POLL_INTERVAL_MS = 800
/** Stop polling after this many failed/empty polls in a row to avoid hot loops on transient errors. */
const POLL_MAX_TICKS = 200

/**
 * Top sold cards / graded cards / sealed items on eBay.fr via the background
 * worker: ``POST /ebay/market/sold-top`` then polling ``GET /ebay/market/sold-top/{job_id}``.
 *
 * Exposes live progress (``pagesDone``, ``pagesTotal``, ``totalObservedSoFar``) and
 * guards against stale jobs (a new submit drops in-flight polls).
 *
 * @returns Reactive state plus ``load``, ``cancel``, and ``reset``.
 */
export function useEbaySoldTop() {
  const { $api } = useNuxtApp() as unknown as { $api: AxiosInstance }

  const loading: Ref<boolean> = ref(false)
  const error: Ref<string | null> = ref(null)
  const result: Ref<EbaySoldTopResultBody | null> = ref(null)
  const ebaySearchUrl: Ref<string | null> = ref(null)

  const status: Ref<EbaySoldTopStatus> = ref('idle')
  const pagesDone: Ref<number> = ref(0)
  const pagesTotal: Ref<number> = ref(0)
  const totalObservedSoFar: Ref<number> = ref(0)
  const cached: Ref<boolean> = ref(false)
  /** Streaming snapshot of in-window items collected so far during the job. */
  const partialItems: Ref<EbaySoldTopItem[]> = ref([])

  /** Active job id — when changed by ``load``, in-flight polls are dropped. */
  const activeJobId: Ref<string | null> = ref(null)
  let pollTimer: ReturnType<typeof setTimeout> | null = null

  /**
   *
   */
  function clearPollTimer(): void {
    if (pollTimer !== null) {
      clearTimeout(pollTimer)
      pollTimer = null
    }
  }

  /**
   *
   */
  function applyEnvelope(env: JobEnvelope): void {
    pagesDone.value = env.pages_done
    pagesTotal.value = env.pages_requested
    totalObservedSoFar.value = env.total_observed
    status.value = env.status
    ebaySearchUrl.value = env.ebay_sold_search_url ?? null
    if (Array.isArray(env.partial_items)) {
      partialItems.value = env.partial_items
    }
    if (env.result) {
      result.value = env.result
    }
    if (env.error) {
      error.value = env.error
    }
  }

  /**
   * Submits a new job (cancels any in-flight job) and polls until completion.
   *
   * @param input - Search parameters.
   * @returns {Promise<EbaySoldTopResultBody | null>} Final payload or ``null`` on error / cancelled.
   */
  async function load(input: EbaySoldTopInput): Promise<EbaySoldTopResultBody | null> {
    clearPollTimer()
    activeJobId.value = null
    loading.value = true
    error.value = null
    result.value = null
    status.value = 'pending'
    pagesDone.value = 0
    pagesTotal.value = input.pages ?? 10
    totalObservedSoFar.value = 0
    cached.value = false
    partialItems.value = []

    let env: JobEnvelope
    try {
      const { data } = await $api.post<JobEnvelope>(
        '/ebay/market/sold-top',
        {
          q: input.q.trim(),
          window_hours: input.windowHours,
          pages: input.pages ?? 10,
          scrape_limit: input.scrapeLimit ?? 600,
          top_limit: input.topLimit ?? 20,
          min_count: input.minCount ?? 1,
          language: input.language ?? null,
        },
        { timeout: 30_000 },
      )
      env = data
    } catch (err: unknown) {
      error.value = apiErrorMessage(err)
      loading.value = false
      status.value = 'failed'
      return null
    }

    const jobId = env.job_id
    activeJobId.value = jobId
    cached.value = !!env.cached
    applyEnvelope(env)

    if (env.status === 'completed' || env.status === 'failed') {
      loading.value = false
      return env.result
    }

    return new Promise<EbaySoldTopResultBody | null>((resolve) => {
      let ticksLeft = POLL_MAX_TICKS

      const poll = async (): Promise<void> => {
        if (jobId !== activeJobId.value) {
          resolve(null)
          return
        }
        try {
          const { data } = await $api.get<JobEnvelope>(`/ebay/market/sold-top/${jobId}`, {
            timeout: 15_000,
          })
          if (jobId !== activeJobId.value) {
            resolve(null)
            return
          }
          applyEnvelope(data)
          if (data.status === 'completed' || data.status === 'failed') {
            loading.value = false
            resolve(data.result)
            return
          }
          ticksLeft -= 1
          if (ticksLeft <= 0) {
            loading.value = false
            error.value = error.value ?? 'Timeout — the job is taking too long to finish.'
            resolve(result.value)
            return
          }
          pollTimer = setTimeout(() => {
            void poll()
          }, POLL_INTERVAL_MS)
        } catch (err: unknown) {
          if (jobId !== activeJobId.value) {
            resolve(null)
            return
          }
          error.value = apiErrorMessage(err)
          loading.value = false
          status.value = 'failed'
          resolve(null)
        }
      }

      pollTimer = setTimeout(() => {
        void poll()
      }, POLL_INTERVAL_MS)
    })
  }

  /**
   * Stops polling and forgets the current job. The server job may keep running
   * (and may still populate the TTL cache for later submits); we simply stop
   * waiting for its result.
   *
   * @returns {void} Nothing.
   */
  function cancel(): void {
    clearPollTimer()
    activeJobId.value = null
    if (status.value === 'pending' || status.value === 'running') {
      status.value = 'idle'
    }
    loading.value = false
  }

  /**
   * Resets all state (useful when unmounting the page).
   *
   * @returns {void} Nothing.
   */
  function reset(): void {
    cancel()
    result.value = null
    error.value = null
    ebaySearchUrl.value = null
    pagesDone.value = 0
    pagesTotal.value = 0
    totalObservedSoFar.value = 0
    cached.value = false
    partialItems.value = []
    status.value = 'idle'
  }

  return {
    loading,
    error,
    result,
    ebaySearchUrl,
    status,
    pagesDone,
    pagesTotal,
    totalObservedSoFar,
    cached,
    partialItems,
    load,
    cancel,
    reset,
  }
}
