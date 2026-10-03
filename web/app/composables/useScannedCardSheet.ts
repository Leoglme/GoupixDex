import type { Ref } from 'vue'
import type { ScanDirection, ScanEvent } from '~/composables/useScanStream'
import type { ScanMatchDecision } from '~/types/ScanMatch'
import type {
  ScannedCard,
  ScannedCardAdd,
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
 * @returns {ScannedCardSheet} Carte affichée, ouverture, confirmation, annulation du dernier ajout et fermeture de la fiche.
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
      actionBinderId: null,
      actionEventId: null,
      actionError: null,
      addsFromSheet: [],
      isUndoingLastAdd: false,
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
    if (card.actionBinderId !== null) {
      loadScannedCardPreview(card)
    }
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
      reloadPreviewThenResetAction(card)
    }, DONE_STATE_DURATION_MS)
  }

  /**
   * Relit la fiche de la carte, puis remet ses boutons au repos si aucune autre action n'a été lancée entre-temps.
   * @param {ScannedCard} card - Carte affichée dont l'action a abouti.
   * @returns {Promise<void>} Résolue une fois la fiche relue.
   */
  async function reloadPreviewThenResetAction(card: ScannedCard): Promise<void> {
    await loadScannedCardPreview(card)
    if (scannedCard.value === card && card.action === 'done') {
      card.action = 'idle'
      card.actionBinderId = null
    }
  }

  /**
   * Ajoute (ou retire) un exemplaire de la carte affichée ; l'issue arrive par le flux d'événements de scan.
   * @param {number | null} binderId - Classeur où ranger l'exemplaire ajouté, `null` pour la collection seule.
   * @returns {Promise<void>} Résolue quand la demande est partie (ou a échoué).
   */
  async function confirmScannedCardAction(binderId: number | null = null): Promise<void> {
    const card: ScannedCard | null = scannedCard.value
    const isTapTooSoonAfterCardSwitch: boolean = Date.now() - shownAt < CARD_SWITCH_TAP_GUARD_MS
    if (!card || card.action === 'pending' || isTapTooSoonAfterCardSwitch) {
      return
    }

    clearActionTimers()
    const eventId: string = `sheet-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`
    card.action = 'pending'
    card.actionBinderId = binderId
    card.actionEventId = eventId
    card.actionError = null
    actionTimeoutTimer = setTimeout((): void => {
      failScannedCardAction(eventId, 'Sans réponse du serveur, réessayez.')
    }, ACTION_TIMEOUT_MS)

    try {
      await dependencies.commitMatchedScan(
        card.decision.tcgdexCardId,
        card.decision.language,
        card.direction,
        eventId,
        binderId,
      )
    } catch (error: unknown) {
      failScannedCardAction(eventId, apiErrorMessage(error))
    }
  }

  /**
   * Annule le dernier exemplaire ajouté depuis la fiche : il quitte la collection et le classeur où il avait été rangé.
   * @returns {Promise<boolean>} `true` quand l'ajout est annulé, `false` s'il n'y avait rien à annuler ou si l'annulation a échoué.
   */
  async function undoLastScannedCardAdd(): Promise<boolean> {
    const card: ScannedCard | null = scannedCard.value
    const lastAdd: ScannedCardAdd | undefined = card?.addsFromSheet.at(-1)
    if (!card || !lastAdd || card.action === 'pending' || card.isUndoingLastAdd) {
      return false
    }

    card.isUndoingLastAdd = true
    card.actionError = null
    try {
      await dependencies.undoScanEvent(lastAdd.eventId)
    } catch (error: unknown) {
      card.actionError = `Annulation impossible : ${apiErrorMessage(error)}`
      return false
    } finally {
      card.isUndoingLastAdd = false
    }

    card.addsFromSheet = card.addsFromSheet.filter((add: ScannedCardAdd): boolean => add !== lastAdd)
    card.ownedQuantity = Math.max(0, (card.ownedQuantity ?? 0) - 1)
    if (scannedCard.value === card && card.action === 'done') {
      clearActionTimers()
      card.action = 'idle'
      card.actionBinderId = null
    }
    loadScannedCardPreview(card)
    return true
  }

  /**
   * Ferme la fiche sans annuler les exemplaires ajoutés depuis elle.
   * @returns {void}
   */
  function dismissScannedCard(): void {
    clearActionTimers()
    scannedCard.value = null
  }

  /**
   * Oublie les ajouts annulés depuis la liste des scans, puis relit la fiche.
   * @param {ScannedCard} card - Carte affichée.
   * @param {ScanEvent[]} events - Scans de la liste.
   * @returns {void}
   */
  function forgetAddsUndoneFromScanList(card: ScannedCard, events: ScanEvent[]): void {
    if (card.isUndoingLastAdd) {
      return
    }
    const listedEventIds: Set<string> = new Set(events.map((event: ScanEvent): string => event.event_id))
    const addsStillListed: ScannedCardAdd[] = card.addsFromSheet.filter((add: ScannedCardAdd): boolean =>
      listedEventIds.has(add.eventId),
    )
    if (addsStillListed.length === card.addsFromSheet.length) {
      return
    }
    card.addsFromSheet = addsStillListed
    loadScannedCardPreview(card)
  }

  watch(dependencies.events, (events: ScanEvent[]): void => {
    const card: ScannedCard | null = scannedCard.value
    if (!card) {
      return
    }
    forgetAddsUndoneFromScanList(card, events)
    if (card.action !== 'pending' || !card.actionEventId) {
      return
    }
    const outcome: ScanEvent | undefined = events.find(
      (event: ScanEvent): boolean => event.event_id === card.actionEventId,
    )
    if (outcome?.status === 'added') {
      card.addsFromSheet = [
        ...card.addsFromSheet,
        { eventId: card.actionEventId, binderName: outcome.binder_placement?.binder_name ?? null },
      ]
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

  return { scannedCard, showScannedCard, confirmScannedCardAction, undoLastScannedCardAdd, dismissScannedCard }
}
