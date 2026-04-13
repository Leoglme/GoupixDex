<script setup lang="ts">
type Phase = 'stack' | 'lift' | 'sold' | 'exit'
type StackRole = 'back' | 'mid' | 'front'

const DURATION = {
  stack: 1500,
  lift: 900,
  sold: 2000,
  exit: 700
} as const

const phase = ref<Phase>('stack')
const reduceMotion = ref(false)

/** Rôle de chaque slot physique0,1,2 (pile réelle — rotation après chaque vente). */
const slotRole = ref<StackRole[]>(['back', 'mid', 'front'])
const slotVariant = ref([0, 1, 2])
let nextVariantId = 3

const teleportSlot = ref<number | null>(null)
const noTransition = ref(false)
const saleCycle = ref(0)

const vphase = computed(() => (reduceMotion.value ? 'sold' : phase.value))

const accentGradients = [
  'from-primary/25 via-elevated to-secondary-400/20',
  'from-secondary-400/25 via-elevated to-primary/25',
  'from-primary/35 via-secondary-400/15 to-default/35'
] as const

const ringByVariant = [
  'ring-default/70',
  'ring-primary/40',
  'ring-secondary-400/45'
] as const

const footerAccents = [
  'bg-primary/45',
  'bg-secondary-400/50',
  'bg-primary/35'
] as const

let timeoutId: ReturnType<typeof setTimeout> | null = null
let mediaQuery: MediaQueryList | null = null
let onMqChange: (() => void) | null = null

function clearSequence() {
  if (timeoutId != null) {
    clearTimeout(timeoutId)
    timeoutId = null
  }
}

function zForSlot(slotIdx: number): number {
  const r = slotRole.value[slotIdx]
  let z = r === 'front' ? 30 : r === 'mid' ? 20 : 10
  if (r === 'front' && phase.value === 'exit') {
    z += 5
  }
  return z
}

function slotTiming(slotIdx: number) {
  if (noTransition.value || teleportSlot.value === slotIdx) {
    return '!duration-0'
  }
  if (!reduceMotion.value && phase.value === 'exit') {
    return 'duration-[700ms] ease-in-out'
  }
  return 'duration-[850ms] ease-in-out'
}

function poseForSlot(slotIdx: number): string {
  if (reduceMotion.value) {
    const r = slotRole.value[slotIdx]
    if (r === 'front') {
      return '-translate-y-2 scale-[1.04] rotate-[-2.5deg] shadow-xl ring-success/55'
    }
    if (r === 'mid') {
      return 'translate-x-2 translate-y-2 rotate-[4deg] opacity-95 shadow-sm'
    }
    return 'translate-x-[1.125rem] translate-y-3 rotate-[8deg] opacity-90 shadow-sm'
  }

  const r = slotRole.value[slotIdx]
  const p = phase.value
  const v = slotVariant.value[slotIdx] % 3
  const ring = ringByVariant[v]

  if (r === 'back') {
    if (p === 'exit') {
      return `translate-x-2 translate-y-2 rotate-[4deg] scale-100 opacity-100 shadow-sm ring-2 ${ring}`
    }
    return `translate-x-[1.125rem] translate-y-3 rotate-[8deg] scale-100 opacity-100 shadow-sm ring-2 ${ring}`
  }

  if (r === 'mid') {
    const base = 'translate-x-2 translate-y-2 rotate-[4deg] scale-100 opacity-100 shadow-sm'
    if (p === 'exit') {
      return `translate-x-0 translate-y-0 rotate-[-2.5deg] scale-100 opacity-100 shadow-md ring-2 ${ring}`
    }
    return `${base} ring-2 ${ring}`
  }

  /* front */
  if (p === 'stack') {
    return `translate-x-0 translate-y-0 rotate-[-2.5deg] scale-100 shadow-md ring-2 ${ring}`
  }
  if (p === 'lift') {
    return `-translate-y-3 scale-[1.04] rotate-0 shadow-lg ring-2 ring-primary/45`
  }
  if (p === 'sold') {
    return `-translate-y-4 scale-[1.06] rotate-0 shadow-xl ring-2 ring-success/55`
  }
  /* exit */
  return 'translate-x-[125%] translate-y-6 rotate-[12deg] opacity-0 scale-90 shadow-xl ring-2 ring-success/50'
}

function showOverlayOnSlot(slotIdx: number) {
  if (reduceMotion.value) {
    return slotRole.value[slotIdx] === 'front'
  }
  const isFront = slotRole.value[slotIdx] === 'front'
  return isFront && (phase.value === 'sold' || phase.value === 'exit')
}

function accentForSlot(slotIdx: number) {
  return accentGradients[slotVariant.value[slotIdx] % 3]
}

function footerForSlot(slotIdx: number) {
  return footerAccents[slotVariant.value[slotIdx] % 3]
}

function stepLift() {
  clearSequence()
  phase.value = 'lift'
  timeoutId = setTimeout(stepSold, DURATION.lift)
}

function stepSold() {
  clearSequence()
  phase.value = 'sold'
  saleCycle.value += 1
  timeoutId = setTimeout(stepExit, DURATION.sold)
}

function stepExit() {
  clearSequence()
  phase.value = 'exit'
  timeoutId = setTimeout(afterExit, DURATION.exit)
}

function afterExit() {
  const roles = [...slotRole.value]
  const bi = roles.indexOf('back')
  const mi = roles.indexOf('mid')
  const fi = roles.indexOf('front')

  roles[bi] = 'mid'
  roles[mi] = 'front'
  roles[fi] = 'back'
  slotVariant.value[fi] = nextVariantId++
  slotRole.value = roles

  teleportSlot.value = fi
  noTransition.value = true
  phase.value = 'stack'

  nextTick(() => {
    teleportSlot.value = null
    noTransition.value = false
    stepStack()
  })
}

function stepStack() {
  clearSequence()
  phase.value = 'stack'
  timeoutId = setTimeout(stepLift, DURATION.stack)
}

function applyReducedMotion(matches: boolean) {
  reduceMotion.value = matches
  clearSequence()
  noTransition.value = false
  teleportSlot.value = null
  if (matches) {
    slotRole.value = ['back', 'mid', 'front']
    slotVariant.value = [0, 1, 2]
    phase.value = 'sold'
    return
  }
  slotRole.value = ['back', 'mid', 'front']
  slotVariant.value = [0, 1, 2]
  nextVariantId = 3
  stepStack()
}

onMounted(() => {
  if (!import.meta.client) {
    return
  }
  mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
  applyReducedMotion(mediaQuery.matches)
  onMqChange = () => applyReducedMotion(mediaQuery!.matches)
  mediaQuery.addEventListener('change', onMqChange)
})

onBeforeUnmount(() => {
  clearSequence()
  if (mediaQuery && onMqChange) {
    mediaQuery.removeEventListener('change', onMqChange)
  }
  mediaQuery = null
  onMqChange = null
})

const slotIndices = [0, 1, 2] as const
</script>

<template>
  <div
    class="relative mx-auto w-full max-w-[13.5rem] select-none"
    :data-phase="vphase"
    aria-hidden="true"
  >
    <div class="relative mx-auto aspect-[5/7] w-36 overflow-visible py-1 sm:w-40">
      <div
        v-for="s in slotIndices"
        :key="s"
        class="absolute inset-0 flex flex-col overflow-hidden rounded-xl bg-elevated transition-all ease-in-out"
        :class="[slotTiming(s), poseForSlot(s)]"
        :style="{ zIndex: zForSlot(s) }"
      >
        <div
          class="relative m-2 flex flex-1 flex-col rounded-lg bg-linear-to-br"
          :class="accentForSlot(s)"
        >
          <div class="m-2 h-2 w-8 rounded-full bg-default/40" />
          <div class="mx-2 mt-1 flex flex-1 flex-col justify-center gap-1.5 px-2">
            <div class="h-1.5 w-full rounded bg-default/30" />
            <div class="h-1.5 w-[80%] rounded bg-default/25" />
            <div class="h-1.5 w-[60%] rounded bg-default/20" />
          </div>
        </div>
        <div class="flex items-center justify-between gap-2 border-t border-default/60 bg-default/40 px-2.5 py-2">
          <div class="h-2 w-12 rounded bg-default/35" />
          <div class="h-2 w-6 rounded" :class="footerForSlot(s)" />
        </div>

        <Transition
          enter-active-class="transition duration-500 ease-out"
          enter-from-class="opacity-0 scale-[0.96]"
          enter-to-class="opacity-100 scale-100"
          leave-active-class="transition duration-300 ease-in"
          leave-from-class="opacity-100"
          leave-to-class="opacity-0"
        >
          <div
            v-if="showOverlayOnSlot(s)"
            :key="`sale-${saleCycle}-slot-${s}`"
            class="absolute inset-0 z-20 flex flex-col items-center justify-center gap-2 rounded-xl bg-default/50 backdrop-blur-[3px]"
          >
            <span
              class="flex size-11 items-center justify-center rounded-full bg-success/20 text-success ring-2 ring-success/50"
            >
              <UIcon name="i-lucide-check" class="size-6" />
            </span>
            <UBadge
              color="success"
              variant="subtle"
              size="sm"
              class="font-semibold"
            >
              Vendu
            </UBadge>
          </div>
        </Transition>
      </div>
    </div>
  </div>
</template>
