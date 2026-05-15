import type {
  CardmarketBasketMissing,
  CardmarketBasketPick,
  CardmarketBasketSellerGroup,
  CardmarketBasketSuggestion,
  CardmarketCardRaw,
} from '~/types/CardmarketSearch'

/**
 * Optimiser knobs (mirrors the user choices in the Advisor card).
 */
export interface SuggestBasketOptions {
  /** Total budget the basket must not exceed (EUR). */
  budgetEur: number
  /**
   * Hard floor: when accepting a **new** seller (not already in the basket), they must
   * bring at least this many still-uncovered cards in one pick. Existing sellers can
   * always add a single card (no extra package, no extra shipping fee).
   * Default: 2.
   */
  minPicksPerNewSeller?: number
  /**
   * Virtual shipping penalty (EUR) applied when scoring a *new* seller's ratio
   * cards / cost. Does NOT add to the displayed total — it just shrinks the ratio so
   * existing sellers and bigger picks win the tie. Default: 3.
   */
  newSellerPenaltyEur?: number
  /**
   * Hard cap on the number of distinct sellers (0 / undefined = no cap).
   */
  maxSellers?: number
  /**
   * Reject any individual card whose price at a seller is more than this percentage
   * above the cheapest offer for that card across all sellers (e.g. `50` skips cards
   * priced at more than +50 % vs min). `null`/`undefined` = no filter. Default: null.
   */
  maxOverpayPercentPerCard?: number | null
  /**
   * If true, run a second pass relaxing `minPicksPerNewSeller` to 1 — single-card
   * sellers are then allowed to fill the remaining budget at the cost of extra
   * shipping fees. Default: false.
   */
  allowSinglePickSellers?: boolean
}

/** Internal: seller -> code -> cheapest price proposed by that seller for that code. */
type SellerOfferIndex = Map<string, Map<string, number>>

const EPSILON = 1e-9

function indexOffersBySeller(cards: CardmarketCardRaw[]): SellerOfferIndex {
  const index: SellerOfferIndex = new Map()
  for (const card of cards) {
    const code = String(card?.code || '').trim()
    if (!code) {
      continue
    }
    const offers = Array.isArray(card.offers) ? card.offers : []
    for (const offer of offers) {
      const seller = String(offer?.seller_name || '').trim()
      const price = typeof offer?.price_eur === 'number' ? offer.price_eur : Number(offer?.price_eur)
      if (!seller || !Number.isFinite(price) || price < 0) {
        continue
      }
      let cardMap = index.get(seller)
      if (!cardMap) {
        cardMap = new Map()
        index.set(seller, cardMap)
      }
      const current = cardMap.get(code)
      if (current === undefined || price < current) {
        cardMap.set(code, price)
      }
    }
  }
  return index
}

function cheapestPriceByCode(cards: CardmarketCardRaw[]): Map<string, number | null> {
  const out = new Map<string, number | null>()
  for (const card of cards) {
    const code = String(card?.code || '').trim()
    if (!code) {
      continue
    }
    const offers = Array.isArray(card.offers) ? card.offers : []
    let best: number | null = null
    for (const offer of offers) {
      const price = typeof offer?.price_eur === 'number' ? offer.price_eur : Number(offer?.price_eur)
      if (!Number.isFinite(price) || price < 0) {
        continue
      }
      if (best === null || price < best) {
        best = price
      }
    }
    out.set(code, best)
  }
  return out
}

interface Candidate {
  seller: string
  pick: Map<string, number>
  pickCost: number
  isExisting: boolean
}

/**
 * Tells whether this seller's price for `code` is acceptable (≤ min × (1 + cap%)).
 */
function priceWithinOverpayCap(
  price: number,
  cheapest: number | null | undefined,
  maxOverpayPercentPerCard: number | null,
): boolean {
  if (maxOverpayPercentPerCard === null) {
    return true
  }
  if (cheapest === null || cheapest === undefined || cheapest <= 0) {
    return true
  }
  const overpayPct = ((price - cheapest) / cheapest) * 100
  return overpayPct <= maxOverpayPercentPerCard + EPSILON
}

/**
 * Pick from this seller, restricted to remaining budget.
 * Drops the most expensive cards first until the cost fits, so the basket stays under budget.
 *
 * The `maxOverpayPercentPerCard` cap is intentionally **not** applied to sellers already
 * in the basket: their shipping fee is already paid, so any extra card at any price is
 * pure value vs. opening a new seller (= new package).
 */
function buildCandidate(
  seller: string,
  sellerOffers: Map<string, number>,
  uncovered: Set<string>,
  remainingBudget: number,
  isExisting: boolean,
  cheapestByCode: Map<string, number | null>,
  maxOverpayPercentPerCard: number | null,
): Candidate | null {
  const effectiveCap = isExisting ? null : maxOverpayPercentPerCard
  const candidates: { code: string; price: number }[] = []
  for (const code of uncovered) {
    const price = sellerOffers.get(code)
    if (price === undefined) {
      continue
    }
    if (!priceWithinOverpayCap(price, cheapestByCode.get(code), effectiveCap)) {
      continue
    }
    candidates.push({ code, price })
  }
  if (candidates.length === 0) {
    return null
  }
  candidates.sort((a, b) => a.price - b.price)
  const pick = new Map<string, number>()
  let pickCost = 0
  for (const { code, price } of candidates) {
    if (pickCost + price <= remainingBudget + EPSILON) {
      pick.set(code, price)
      pickCost += price
    }
  }
  if (pick.size === 0) {
    return null
  }
  return { seller, pick, pickCost, isExisting }
}

/**
 * Effective ratio "new cards per euro spent" — primary score for the greedy step.
 * For a NEW seller, the cost is inflated by `newSellerPenaltyEur` (virtual shipping)
 * so existing sellers naturally win ties when their ratio is comparable.
 */
function ratioCardsPerEuro(c: Candidate, newSellerPenaltyEur: number): number {
  const effectiveCost = c.pickCost + (c.isExisting ? 0 : newSellerPenaltyEur)
  if (effectiveCost <= EPSILON) {
    return c.pick.size * 1e9
  }
  return c.pick.size / effectiveCost
}

/**
 * Strict ordering on two candidates (negative when `a` is preferred).
 * Priority:
 *   1. higher cards-per-euro ratio,
 *   2. existing seller,
 *   3. more new cards,
 *   4. lower raw cost.
 */
function compareCandidates(a: Candidate, b: Candidate, newSellerPenaltyEur: number): number {
  const aRatio = ratioCardsPerEuro(a, newSellerPenaltyEur)
  const bRatio = ratioCardsPerEuro(b, newSellerPenaltyEur)
  if (Math.abs(aRatio - bRatio) > 1e-6) {
    return aRatio > bRatio ? -1 : 1
  }
  if (a.isExisting !== b.isExisting) {
    return a.isExisting ? -1 : 1
  }
  if (a.pick.size !== b.pick.size) {
    return a.pick.size > b.pick.size ? -1 : 1
  }
  if (Math.abs(a.pickCost - b.pickCost) > 1e-6) {
    return a.pickCost < b.pickCost ? -1 : 1
  }
  return 0
}

interface PickBestArgs {
  sellerIndex: SellerOfferIndex
  uncovered: Set<string>
  selectedSellers: Map<string, Map<string, number>>
  budgetRemaining: number
  cheapestByCode: Map<string, number | null>
  newSellerPenaltyEur: number
  maxSellers: number
  /** Lower bound on `pick.size` for a NEW seller (existing sellers accept any pick.size ≥ 1). */
  minPicksPerNewSeller: number
  maxOverpayPercentPerCard: number | null
}

function pickBestCandidate(args: PickBestArgs): Candidate | null {
  let best: Candidate | null = null
  for (const [seller, offers] of args.sellerIndex) {
    const isExisting = args.selectedSellers.has(seller)
    if (!isExisting && args.maxSellers > 0 && args.selectedSellers.size >= args.maxSellers) {
      continue
    }
    const cand = buildCandidate(
      seller,
      offers,
      args.uncovered,
      args.budgetRemaining,
      isExisting,
      args.cheapestByCode,
      args.maxOverpayPercentPerCard,
    )
    if (!cand) {
      continue
    }
    const minSize = isExisting ? 1 : Math.max(1, args.minPicksPerNewSeller)
    if (cand.pick.size < minSize) {
      continue
    }
    if (!best || compareCandidates(cand, best, args.newSellerPenaltyEur) < 0) {
      best = cand
    }
  }
  return best
}

/**
 * Greedy basket optimiser under a fixed budget.
 *
 * Goal: cover as many cards as possible while limiting the number of distinct sellers
 * AND keeping a strong "cards per euro" ratio (so cheap, decent-volume sellers beat
 * pricey big-volume sellers).
 *
 * Strategy (2 passes):
 *   - Pass 1: every NEW seller must bring at least `minPicksPerNewSeller` cards
 *     (default 2). Existing sellers can keep adding 1+ cards (no extra package).
 *   - Pass 2 (opt-in via `allowSinglePickSellers`): relax to 1 card per new seller
 *     and fill the remaining budget with cheapest available cards.
 *
 * At each step we pick the seller with the **best ratio cards / euro** (virtual
 * shipping penalty applied to new sellers); tie-broken by reuse → more cards → lower
 * cost. The optional `maxOverpayPercentPerCard` filter discards individual cards
 * priced too far above the absolute minimum, which guards against pricey sellers
 * dragging the budget down.
 * @param cards   `last_result.cards[]` payload from the worker.
 * @param options Budget + knobs (see {@link SuggestBasketOptions}).
 * @returns       Suggested basket grouped by seller, with missing cards explained.
 */
export function suggestCardmarketBasket(
  cards: CardmarketCardRaw[],
  options: SuggestBasketOptions,
): CardmarketBasketSuggestion {
  const budgetEur = Math.max(0, Number(options.budgetEur) || 0)
  const newSellerPenaltyEur = Math.max(0, Number(options.newSellerPenaltyEur ?? 3) || 0)
  const maxSellers = Math.max(0, Math.floor(Number(options.maxSellers ?? 0) || 0))
  const minPicksPerNewSeller = Math.max(1, Math.floor(Number(options.minPicksPerNewSeller ?? 2) || 1))
  const allowSinglePickSellers = options.allowSinglePickSellers === true
  const maxOverpayPercentPerCard =
    options.maxOverpayPercentPerCard === null ||
    options.maxOverpayPercentPerCard === undefined ||
    !Number.isFinite(Number(options.maxOverpayPercentPerCard))
      ? null
      : Math.max(0, Number(options.maxOverpayPercentPerCard))

  const cardsList: CardmarketCardRaw[] = Array.isArray(cards) ? cards : []
  const cheapestByCode = cheapestPriceByCode(cardsList)
  const cardMeta = new Map<string, { product_name: string | null; product_url: string | null }>()
  const allCodes: string[] = []
  for (const card of cardsList) {
    const code = String(card?.code || '').trim()
    if (!code || cardMeta.has(code)) {
      continue
    }
    cardMeta.set(code, {
      product_name: typeof card.product_name === 'string' ? card.product_name : null,
      product_url: typeof card.product_url === 'string' ? card.product_url : null,
    })
    allCodes.push(code)
  }

  const sellerIndex = indexOffersBySeller(cardsList)
  const uncovered = new Set<string>(allCodes)
  const selectedSellers = new Map<string, Map<string, number>>()
  let totalPrice = 0

  while (uncovered.size > 0) {
    const cand = pickBestCandidate({
      sellerIndex,
      uncovered,
      selectedSellers,
      budgetRemaining: budgetEur - totalPrice,
      cheapestByCode,
      newSellerPenaltyEur,
      maxSellers,
      minPicksPerNewSeller,
      maxOverpayPercentPerCard,
    })
    if (!cand) {
      break
    }
    applyCandidate(cand, selectedSellers, uncovered)
    totalPrice += cand.pickCost
  }

  totalPrice = drainBudgetWithExistingSellers({
    sellerIndex,
    uncovered,
    selectedSellers,
    budgetEur,
    totalPrice,
  })

  if (allowSinglePickSellers && uncovered.size > 0) {
    while (uncovered.size > 0) {
      const cand = pickBestCandidate({
        sellerIndex,
        uncovered,
        selectedSellers,
        budgetRemaining: budgetEur - totalPrice,
        cheapestByCode,
        newSellerPenaltyEur,
        maxSellers,
        minPicksPerNewSeller: 1,
        maxOverpayPercentPerCard,
      })
      if (!cand) {
        break
      }
      applyCandidate(cand, selectedSellers, uncovered)
      totalPrice += cand.pickCost
    }
    totalPrice = drainBudgetWithExistingSellers({
      sellerIndex,
      uncovered,
      selectedSellers,
      budgetEur,
      totalPrice,
    })
  }

  return buildResult({
    budgetEur,
    cardsList,
    cardMeta,
    cheapestByCode,
    selectedSellers,
    uncovered,
    totalPrice,
    sellerIndex,
    maxOverpayPercentPerCard,
  })
}

function applyCandidate(
  cand: Candidate,
  selectedSellers: Map<string, Map<string, number>>,
  uncovered: Set<string>,
): void {
  const existing = selectedSellers.get(cand.seller)
  const merged = existing ?? new Map<string, number>()
  for (const [code, price] of cand.pick) {
    merged.set(code, price)
    uncovered.delete(code)
  }
  selectedSellers.set(cand.seller, merged)
}

interface DrainArgs {
  sellerIndex: SellerOfferIndex
  uncovered: Set<string>
  selectedSellers: Map<string, Map<string, number>>
  budgetEur: number
  totalPrice: number
}

/**
 * "Drain" phase — once the greedy is done, keep adding the **cheapest still-uncovered
 * card available at one of the already-selected sellers**, ignoring the overpay cap
 * (their shipping is sunk cost). Iterates until budget exhausted or no candidate left.
 *
 * Maximises card count for the remaining budget without opening any new seller.
 */
function drainBudgetWithExistingSellers(args: DrainArgs): number {
  const { sellerIndex, uncovered, selectedSellers, budgetEur } = args
  let totalPrice = args.totalPrice
  if (uncovered.size === 0 || selectedSellers.size === 0) {
    return totalPrice
  }

  while (uncovered.size > 0) {
    let best: { code: string; seller: string; price: number } | null = null
    for (const code of uncovered) {
      let bestForCode: { seller: string; price: number } | null = null
      for (const seller of selectedSellers.keys()) {
        const offers = sellerIndex.get(seller)
        if (!offers) {
          continue
        }
        const price = offers.get(code)
        if (price === undefined) {
          continue
        }
        if (totalPrice + price > budgetEur + EPSILON) {
          continue
        }
        if (!bestForCode || price < bestForCode.price) {
          bestForCode = { seller, price }
        }
      }
      if (bestForCode && (!best || bestForCode.price < best.price)) {
        best = { code, seller: bestForCode.seller, price: bestForCode.price }
      }
    }
    if (!best) {
      break
    }
    const cardMap = selectedSellers.get(best.seller)!
    cardMap.set(best.code, best.price)
    uncovered.delete(best.code)
    totalPrice += best.price
  }
  return totalPrice
}

interface BuildResultArgs {
  budgetEur: number
  cardsList: CardmarketCardRaw[]
  cardMeta: Map<string, { product_name: string | null; product_url: string | null }>
  cheapestByCode: Map<string, number | null>
  selectedSellers: Map<string, Map<string, number>>
  uncovered: Set<string>
  totalPrice: number
  sellerIndex: SellerOfferIndex
  maxOverpayPercentPerCard: number | null
}

function buildResult(args: BuildResultArgs): CardmarketBasketSuggestion {
  const {
    budgetEur,
    cardsList,
    cardMeta,
    cheapestByCode,
    selectedSellers,
    uncovered,
    totalPrice,
    sellerIndex,
    maxOverpayPercentPerCard,
  } = args

  const sellers: CardmarketBasketSellerGroup[] = []
  for (const [seller, codeMap] of selectedSellers) {
    const picks: CardmarketBasketPick[] = []
    let subtotal = 0
    for (const [code, price] of codeMap) {
      const meta = cardMeta.get(code) || { product_name: null, product_url: null }
      const cheapest = cheapestByCode.get(code) ?? null
      const deltaEur = cheapest !== null ? round4(price - cheapest) : null
      const isBest = cheapest !== null ? Math.abs(price - cheapest) < EPSILON : false
      const deltaPct =
        cheapest !== null && cheapest > 0 && !isBest ? round4(((price - cheapest) / cheapest) * 100) : null
      picks.push({
        code,
        product_name: meta.product_name,
        product_url: meta.product_url,
        seller_name: seller,
        price_eur: round4(price),
        cheapest_eur: cheapest,
        delta_vs_min_eur: deltaEur,
        delta_vs_min_percent: deltaPct,
        is_best_price: isBest,
      })
      subtotal += price
    }
    picks.sort((a, b) => a.code.localeCompare(b.code))
    sellers.push({ seller_name: seller, picks, subtotal_eur: round4(subtotal) })
  }
  sellers.sort((a, b) => b.picks.length - a.picks.length || a.subtotal_eur - b.subtotal_eur)

  const singlePickSellerCount = sellers.reduce((acc, s) => acc + (s.picks.length === 1 ? 1 : 0), 0)

  const missing: CardmarketBasketMissing[] = []
  for (const code of uncovered) {
    const meta = cardMeta.get(code) || { product_name: null, product_url: null }
    const cheapest = cheapestByCode.get(code) ?? null
    const hasOffer = anySellerHasCode(sellerIndex, code)
    let reason: CardmarketBasketMissing['reason'] = 'no_offer'
    if (hasOffer) {
      reason = 'over_budget'
      if (
        maxOverpayPercentPerCard !== null &&
        !anySellerHasAffordableOffer(sellerIndex, code, cheapest, maxOverpayPercentPerCard)
      ) {
        reason = 'overpriced'
      }
    }
    missing.push({ code, product_name: meta.product_name, cheapest_eur: cheapest, reason })
  }
  missing.sort((a, b) => a.code.localeCompare(b.code))

  const warnings: string[] = []
  if (cardsList.length > 0 && budgetEur <= 0) {
    warnings.push('Budget nul ou invalide — aucun panier possible.')
  }

  return {
    budget_eur: round4(budgetEur),
    total_cards: cardMeta.size,
    covered_cards: cardMeta.size - uncovered.size,
    total_price_eur: round4(totalPrice),
    remaining_budget_eur: round4(Math.max(0, budgetEur - totalPrice)),
    sellers,
    single_pick_seller_count: singlePickSellerCount,
    missing,
    warnings,
  }
}

function anySellerHasCode(sellerIndex: SellerOfferIndex, code: string): boolean {
  for (const offers of sellerIndex.values()) {
    if (offers.has(code)) {
      return true
    }
  }
  return false
}

function anySellerHasAffordableOffer(
  sellerIndex: SellerOfferIndex,
  code: string,
  cheapest: number | null,
  maxOverpayPercentPerCard: number,
): boolean {
  for (const offers of sellerIndex.values()) {
    const price = offers.get(code)
    if (price !== undefined && priceWithinOverpayCap(price, cheapest, maxOverpayPercentPerCard)) {
      return true
    }
  }
  return false
}

function round4(n: number): number {
  return Math.round(n * 10000) / 10000
}
