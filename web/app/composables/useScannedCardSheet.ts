import type { Ref } from 'vue'
import type { ScanDirection, ScanEvent } from '~/composables/useScanStream'
import type { ScanMatchDecision } from '~/types/ScanMatch'
import type {
  ScannedCard,
  ScannedCardPreview,
  ScannedCardSheet,
  ScannedCardSheetDependencies,
} from '~/types/ScannedCardSheet'

const ACTION_TIMEOUT_MS: number = 20_000
const DONE_STATE_DURATION_MS: number = 1_400
const CARD_SWITCH_TAP_GUARD_MS: number = 400

/**
 * Fiche de la carte reconnue par le scanner : aperçu (cote, exemplaires possédés) et ajout ou retrait confirmé au tap.
 * @param {ScannedCardSheetDependencies} dependencies - Flux d'événements de scan et appels API de la page scan.
 * @returns {ScannedCardSheet} Carte affichée, ouverture, confirmation et fermeture de la fiche.
 */
export function useScannedCardSheet(dependencies: ScannedCardSheetDependencies): ScannedCardSheet {
  const scannedCard: Ref<ScannedCard | null> = ref(null)

  let shownAt: number = 0
  let previewRequestCount: number = 0
  let actionTimeoutTimer: ReturnType<typeof setTimeout> | null = null
  let doneStateTimer: ReturnType<typeof setTimeout> | null = null

  /**
   * Arrête les minuteries de l'action en cours (délai de réponse, retour du bouton à l'état normal).
   * @returns {void}
   */
  function clearActionTimers(): void {
    if (actionTimeoutTimer !== null) {
      clearTimeout(actionTimeoutTimer)
      actionTimeoutTimer = null
    }
    if (doneStateTimer !== null) {
      clearTimeout(doneStateTimer)
      doneStateTimer = null
    }
  }

  /**
   * Charge la fiche serveur de la carte affichée ; une réponse arrivée après une plus récente est ignorée.
   * @param {ScannedCard} card - Carte affichée au moment de la demande.
   * @returns {Promise<void>} Résolue quand la fiche est appliquée, ou abandonnée.
   */
  async function loadScannedCardPreview(card: ScannedCard): Promise<void> {
    previewRequestCount += 1
    const requestNumber: number = previewRequestCount
    let preview: ScannedCardPreview | null = null
    try {
      preview = await dependencies.fetchScannedCardPreview(card.decision.tcgdexCardId, card.decision.language)
    } catch {
      preview = null
    }

    const isLatestRequestForDisplayedCard: boolean = requestNumber === previewRequestCount && scannedCard.value === card
    if (!isLatestRequestForDisplayedCard) {
      return
    }

    card.isPreviewLoading = false
    if (preview) {
      card.preview = preview
      card.ownedQuantity = preview.owned_quantity
    }
  }

  /**
   * Affiche la fiche d'une carte tout juste reconnue (remplace la précédente) et charge sa cote.
   * @param {ScanMatchDecision} decision - Carte reconnue sur l'appareil.
   * @param {string} imageUrl - Vignette disponible tout de suite, sans attendre l'API.
   * @param {ScanDirection} direction - `in` pour proposer l'ajout, `out` pour proposer le retrait.
   * @returns {void}
   */
  function showScannedCard(decision: ScanMatchDecision, imageUrl: string, direction: ScanDirection): void {
    clearActionTimers()
    shownAt = Date.now()
    scannedCard.value = {
      decision,
      imageUrl,
      direction,
      preview: null,
      isPreviewLoading: true,
      ownedQuantity: null,
      action: 'idle',
      actionEventId: null,
      actionError: null,
    }
    loadScannedCardPreview(scannedCard.value)
  }

  /**
   * Passe l'action en échec si elle concerne toujours la carte affichée.
   * @param {string} eventId - Événement de l'action échouée.
   * @param {string} message - Explication affichée sous le bouton.
   * @returns {void}
   */
  function failScannedCardAction(eventId: string, message: string): void {
    const card: ScannedCard | null = scannedCard.value
    if (!card || card.actionEventId !== eventId) {
      return
    }
    clearActionTimers()
    card.action = 'failed'
    card.actionError = message
  }

  /**
   * Valide l'action réussie : un exemplaire de plus (ou de moins), puis le bouton redevient utilisable.
   * @param {ScannedCard} card - Carte affichée dont l'action a abouti.
   * @param {number} ownedQuantityChange - `1` après un ajout, `-1` après un retrait.
   * @returns {void}
   */
  function completeScannedCardAction(card: ScannedCard, ownedQuantityChange: number): void {
    clearActionTimers()
    card.action = 'done'
    card.ownedQuantity = Math.max(0, (card.ownedQuantity ?? 0) + ownedQuantityChange)
    doneStateTimer = setTimeout((): void => {
      if (scannedCard.value === card && card.action === 'done') {
        card.action = 'idle'
      }
    }, DONE_STATE_DURATION_MS)
    loadScannedCardPreview(card)
  }

  /**
   * Ajoute (ou retire) un exemplaire de la carte affichée ; l'issue arrive par le flux d'événements de scan.
   * @returns {Promise<void>} Résolue quand la demande est partie (ou a échoué).
   */
  async function confirmScannedCardAction(): Promise<void> {
    const card: ScannedCard | null = scannedCard.value
    const isTapTooSoonAfterCardSwitch: boolean = Date.now() - shownAt < CARD_SWITCH_TAP_GUARD_MS
    if (!card || card.action === 'pending' || isTapTooSoonAfterCardSwitch) {
      return
    }

    clearActionTimers()
    const eventId: string = `sheet-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`
    card.action = 'pending'
    card.actionEventId = eventId
    card.actionError = null
    actionTimeoutTimer = setTimeout((): void => {
      failScannedCardAction(eventId, 'Sans réponse du serveur, réessayez.')
    }, ACTION_TIMEOUT_MS)

    try {
      await dependencies.commitMatchedScan(card.decision.tcgdexCardId, card.decision.language, card.direction, eventId)
    } catch (error: unknown) {
      failScannedCardAction(eventId, apiErrorMessage(error))
    }
  }

  /**
   * Ferme la fiche ; le scanner continue et la rouvrira à la prochaine carte reconnue.
   * @returns {void}
   */
  function dismissScannedCard(): void {
    clearActionTimers()
    scannedCard.value = null
  }

  watch(dependencies.events, (events: ScanEvent[]): void => {
    const card: ScannedCard | null = scannedCard.value
    if (!card || card.action !== 'pending' || !card.actionEventId) {
      return
    }
    const outcome: ScanEvent | undefined = events.find(
      (event: ScanEvent): boolean => event.event_id === card.actionEventId,
    )
    if (outcome?.status === 'added') {
      completeScannedCardAction(card, 1)
    } else if (outcome?.status === 'removed') {
      completeScannedCardAction(card, -1)
    } else if (outcome?.status === 'failed' || outcome?.status === 'not_in_collection') {
      failScannedCardAction(card.actionEventId, outcome.error ?? 'Action impossible, réessayez.')
    }
  })

  onBeforeUnmount((): void => {
    clearActionTimers()
  })

  return { scannedCard, showScannedCard, confirmScannedCardAction, dismissScannedCard }
}
