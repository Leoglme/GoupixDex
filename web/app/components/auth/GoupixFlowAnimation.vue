<script setup lang="ts">
/**
 * Flow orchestration: scan → form → Vinted → stats → sale.
 * Step click: show the matching animation and restart auto-advance.
 */
type FlowStep = 'scan' | 'form' | 'list' | 'stats' | 'sale'

const STEPS: FlowStep[] = ['scan', 'form', 'list', 'stats', 'sale']
const DURATION_MS: Record<FlowStep, number> = {
  scan: 2200,
  form: 3000,
  list: 2100,
  stats: 2400,
  sale: 2200
}
const PAUSE_END_MS = 1600

const stepIndex = ref(0)
const reduceMotion = ref(false)
const formFill = ref(0)

const currentStep = computed(() => STEPS[stepIndex.value])

/** Display label for each step */
const stepLabel: Record<FlowStep, string> = {
  scan: 'Scan carte',
  form: 'Remplissage auto',
  list: 'Publication Vinted',
  stats: 'Stats & marges',
  sale: 'Carte vendue'
}

const timerIds: ReturnType<typeof setTimeout>[] = []
let mediaQuery: MediaQueryList | null = null
let onMqChange: (() => void) | null = null

function clearAllTimers() {
  timerIds.forEach(id => clearTimeout(id))
  timerIds.length = 0
}

function addTimer(fn: () => void, ms: number) {
  const id = setTimeout(fn, ms)
  timerIds.push(id)
  return id
}

function advance() {
  stepIndex.value = (stepIndex.value + 1) % STEPS.length
}

function scheduleFormFill() {
  formFill.value = 0
  if (reduceMotion.value) {
    formFill.value = 4
    return
  }
  addTimer(() => { formFill.value = 1 }, 280)
  addTimer(() => { formFill.value = 2 }, 650)
  addTimer(() => { formFill.value = 3 }, 1100)
  addTimer(() => { formFill.value = 4 }, 1650)
}

function runStep() {
  clearAllTimers()
  const step = STEPS[stepIndex.value]
  if (reduceMotion.value) {
    formFill.value = step === 'form' ? 4 : 0
    return
  }
  if (step === 'form') {
    scheduleFormFill()
  } else {
    formFill.value = 0
  }

  const ms = DURATION_MS[step]
  addTimer(() => {
    if (stepIndex.value === STEPS.length - 1) {
      addTimer(() => {
        advance()
        runStep()
      }, PAUSE_END_MS)
    } else {
      advance()
      runStep()
    }
  }, ms)
}

/** Click: jump to step and restart auto-advance. */
function goToStep(i: number) {
  if (i < 0 || i >= STEPS.length) {
    return
  }
  stepIndex.value = i
  runStep()
}

function applyReducedMotion(matches: boolean) {
  reduceMotion.value = matches
  clearAllTimers()
  stepIndex.value = matches ? STEPS.indexOf('sale') : 0
  if (!matches) {
    runStep()
  } else {
    formFill.value = STEPS[stepIndex.value] === 'form' ? 4 : 0
  }
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
  clearAllTimers()
  if (mediaQuery && onMqChange) {
    mediaQuery.removeEventListener('change', onMqChange)
  }
  mediaQuery = null
  onMqChange = null
})
</script>

<template>
  <div
    class="mx-auto w-full min-w-0 max-w-[36rem] rounded-xl border border-default bg-elevated/60 p-4 shadow-sm ring-1 ring-default/40 sm:max-w-[42rem] sm:p-6 lg:max-w-[46rem]"
  >
    <div
      role="tablist"
      aria-label="Étapes du parcours GoupixDex"
      class="mb-4 grid grid-cols-5 items-stretch gap-x-1 gap-y-1 sm:gap-x-1.5"
    >
      <button
        v-for="(s, i) in STEPS"
        :key="s"
        type="button"
        role="tab"
        :aria-selected="i === stepIndex"
        class="flex min-h-[4.75rem] min-w-0 flex-col items-center justify-center gap-1.5 rounded-lg px-1 py-2 text-center transition-colors hover:bg-elevated/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary sm:min-h-[5rem] sm:px-1.5"
        :class="i === stepIndex ? 'text-highlighted' : 'text-muted'"
        @click="goToStep(i)"
      >
        <span
          class="size-2.5 shrink-0 rounded-full transition-all duration-300 sm:size-3"
          :class="i === stepIndex ? 'scale-110 bg-primary ring-2 ring-primary/30' : 'bg-default/50'"
        />
        <span
          class="max-w-[6.25rem] self-center text-balance text-center text-[0.62rem] font-medium leading-snug sm:max-w-[7rem] sm:text-xs lg:max-w-[8rem]"
        >{{ stepLabel[s] }}</span>
      </button>
    </div>

    <div
      class="relative min-h-[18rem] w-full min-w-0 overflow-hidden rounded-lg border border-default/50 bg-default/30 p-3 sm:min-h-[21.5rem] sm:p-4 lg:min-h-[23.5rem]"
    >
      <Transition
        enter-active-class="transition duration-300 ease-out"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition duration-200 ease-in"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <FlowScanStep
          v-if="currentStep === 'scan'"
          :reduce-motion="reduceMotion"
        />
      </Transition>

      <Transition
        enter-active-class="transition duration-300 ease-out"
        enter-from-class="opacity-0 translate-y-1"
        enter-to-class="opacity-100 translate-y-0"
        leave-active-class="transition duration-200 ease-in"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <FlowFormStep
          v-if="currentStep === 'form'"
          :form-fill="formFill"
        />
      </Transition>

      <Transition
        enter-active-class="transition duration-300 ease-out"
        enter-from-class="opacity-0 scale-95"
        enter-to-class="opacity-100 scale-100"
        leave-active-class="transition duration-200 ease-in"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <FlowListStep
          v-if="currentStep === 'list'"
          :reduce-motion="reduceMotion"
        />
      </Transition>

      <Transition
        enter-active-class="transition duration-300 ease-out"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition duration-200 ease-in"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <FlowStatsStep
          v-if="currentStep === 'stats'"
          :reduce-motion="reduceMotion"
        />
      </Transition>

      <Transition
        enter-active-class="transition duration-300 ease-out"
        enter-from-class="opacity-0 scale-95"
        enter-to-class="opacity-100 scale-100"
        leave-active-class="transition duration-200 ease-in"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <FlowSaleStep
          v-if="currentStep === 'sale'"
          :reduce-motion="reduceMotion"
        />
      </Transition>
    </div>
  </div>
</template>
