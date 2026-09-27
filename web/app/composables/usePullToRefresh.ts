import type { ComputedRef, Ref } from 'vue'
import type { PullToRefresh } from '~/types/PullToRefresh'

const REFRESH_THRESHOLD_PX: number = 72
const MAXIMUM_PULL_DISTANCE_PX: number = 110
const FINGER_TO_INDICATOR_RATIO: number = 0.5
const GESTURE_DIRECTION_SLOP_PX: number = 6

/**
 * Déclenche une actualisation quand on tire l'écran vers le bas depuis le haut de la page, dans l'application installée uniquement.
 * @param {() => void} onRefresh - Actualisation lancée quand le doigt est relâché au-delà du seuil.
 * @returns {PullToRefresh} Distance tirée et état du geste, pour l'indicateur.
 */
export function usePullToRefresh(onRefresh: () => void): PullToRefresh {
  const pullDistance: Ref<number> = ref(0)
  const isPulling: Ref<boolean> = ref(false)
  const isRefreshing: Ref<boolean> = ref(false)

  const pullProgress: ComputedRef<number> = computed((): number =>
    Math.min(1, pullDistance.value / REFRESH_THRESHOLD_PX),
  )
  const hasReachedRefreshThreshold: ComputedRef<boolean> = computed((): boolean => pullProgress.value >= 1)

  let gestureStartX: number = 0
  let gestureStartY: number = 0
  let isGestureFollowed: boolean = false

  /**
   * Vrai dans l'application ouverte depuis l'écran d'accueil, où Safari n'offre pas de « tirer pour actualiser ».
   * @returns {boolean} Vrai en mode application installée.
   */
  function isInstalledApp(): boolean {
    return (
      window.matchMedia('(display-mode: standalone)').matches ||
      ('standalone' in window.navigator && window.navigator.standalone === true)
    )
  }

  /**
   * Vrai quand le doigt se pose sur un contenu déjà défilé : le geste doit alors remonter ce contenu, pas actualiser.
   * @param {Element} touchedElement - Élément sous le doigt.
   * @returns {boolean} Vrai si un conteneur de l'élément n'est pas en haut.
   */
  function isInsideScrolledContent(touchedElement: Element): boolean {
    for (let element: Element | null = touchedElement; element; element = element.parentElement) {
      if (element.scrollTop > 0) {
        return true
      }
    }
    return false
  }

  /**
   * Commence à suivre un doigt posé en haut de la page, hors fenêtres modales.
   * @param {TouchEvent} event - Contact du doigt.
   * @returns {void}
   */
  function onTouchStart(event: TouchEvent): void {
    isGestureFollowed = false
    const touch: Touch | null = event.touches.item(0)
    if (isRefreshing.value || event.touches.length !== 1 || !touch || !isInstalledApp()) {
      return
    }
    if (!(event.target instanceof Element) || event.target.closest('[role="dialog"], [data-no-pull-to-refresh]')) {
      return
    }
    if (isInsideScrolledContent(event.target)) {
      return
    }

    gestureStartX = touch.clientX
    gestureStartY = touch.clientY
    isGestureFollowed = true
  }

  /**
   * Fait descendre l'indicateur avec le doigt, une fois le geste reconnu comme vertical et vers le bas.
   * @param {TouchEvent} event - Déplacement du doigt.
   * @returns {void}
   */
  function onTouchMove(event: TouchEvent): void {
    const touch: Touch | null = event.touches.item(0)
    if (!isGestureFollowed || !touch) {
      return
    }
    const horizontalDistance: number = touch.clientX - gestureStartX
    const verticalDistance: number = touch.clientY - gestureStartY
    if (!isPulling.value) {
      if (
        Math.abs(horizontalDistance) < GESTURE_DIRECTION_SLOP_PX &&
        Math.abs(verticalDistance) < GESTURE_DIRECTION_SLOP_PX
      ) {
        return
      }
      if (verticalDistance <= 0 || Math.abs(horizontalDistance) > verticalDistance) {
        isGestureFollowed = false
        return
      }
      isPulling.value = true
    }

    pullDistance.value = Math.min(MAXIMUM_PULL_DISTANCE_PX, Math.max(0, verticalDistance * FINGER_TO_INDICATOR_RATIO))
    // Sans ça, iOS fait rebondir la page sous l'indicateur.
    if (event.cancelable) {
      event.preventDefault()
    }
  }

  /**
   * Actualise si le doigt est relâché au-delà du seuil, sinon remonte l'indicateur.
   * @returns {void}
   */
  function onTouchEnd(): void {
    isGestureFollowed = false
    if (!isPulling.value) {
      return
    }
    isPulling.value = false

    if (hasReachedRefreshThreshold.value) {
      isRefreshing.value = true
      pullDistance.value = REFRESH_THRESHOLD_PX
      onRefresh()
      return
    }
    pullDistance.value = 0
  }

  onMounted((): void => {
    if (navigator.maxTouchPoints === 0) {
      return
    }
    document.addEventListener('touchstart', onTouchStart, { passive: true })
    document.addEventListener('touchmove', onTouchMove, { passive: false })
    document.addEventListener('touchend', onTouchEnd, { passive: true })
    document.addEventListener('touchcancel', onTouchEnd, { passive: true })
  })

  onBeforeUnmount((): void => {
    document.removeEventListener('touchstart', onTouchStart)
    document.removeEventListener('touchmove', onTouchMove)
    document.removeEventListener('touchend', onTouchEnd)
    document.removeEventListener('touchcancel', onTouchEnd)
  })

  return { pullDistance, pullProgress, isPulling, isRefreshing, hasReachedRefreshThreshold }
}
