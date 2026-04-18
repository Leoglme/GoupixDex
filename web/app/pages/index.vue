<script setup lang="ts">
import logoUrl from '~/assets/images/logo-goupix-dev-256x256.png'

definePageMeta({
  layout: 'auth'
})

useGoupixPageSeo(
  'Scannez vos cartes Pokémon — mise en ligne automatisée sur Vinted et eBay | GoupixDex',
  'Scan photo, prix Cardmarket & TCGPlayer, annonces générées et publication sur Vinted et eBay. Synchronisez aussi votre dressing Vinted (collection, annonces en ligne, ventes) dans votre espace. Tableau de bord et marges.'
)

useSeoMeta({
  keywords: 'pokémon tcg, vinted, synchronisation dressing vinted, ebay, automatisation, cardmarket, tcgplayer, vente cartes pokémon, scan carte pokémon, annonce vinted, annonce ebay, goupixdex'
})

const { isLoggedIn, authResolved } = useAuth()

const reduceMotion = ref(false)
const formFill = ref(0)
const mobileMenuOpen = ref(false)

const heroRef = ref<HTMLElement>()
const sectionRefs = ref<(HTMLElement | undefined)[]>([])
const sellingRef = ref<HTMLElement>()
const ctaRef = ref<HTMLElement>()

let formFillTimers: ReturnType<typeof setTimeout>[] = []
let gsapMatchMediaRevert: (() => void) | undefined

function setSectionRef(el: Element | null, idx: number) {
  if (el) {
    sectionRefs.value[idx] = el as HTMLElement
  }
}

function startFormFillLoop() {
  stopFormFillLoop()
  if (reduceMotion.value) {
    formFill.value = 4
    return
  }
  function cycle() {
    formFill.value = 0
    formFillTimers.push(setTimeout(() => { formFill.value = 1 }, 400))
    formFillTimers.push(setTimeout(() => { formFill.value = 2 }, 900))
    formFillTimers.push(setTimeout(() => { formFill.value = 3 }, 1500))
    formFillTimers.push(setTimeout(() => { formFill.value = 4 }, 2200))
    formFillTimers.push(setTimeout(cycle, 4500))
  }
  cycle()
}

function stopFormFillLoop() {
  formFillTimers.forEach(id => clearTimeout(id))
  formFillTimers = []
}

onMounted(() => {
  if (!import.meta.client) return

  const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
  reduceMotion.value = mq.matches
  mq.addEventListener('change', e => { reduceMotion.value = e.matches })

  startFormFillLoop()

  const { $gsap, $ScrollTrigger } = useNuxtApp()
  const gsap = $gsap as typeof import('gsap')['gsap']
  const ScrollTrigger = $ScrollTrigger as typeof import('gsap/ScrollTrigger')['ScrollTrigger']

  if (reduceMotion.value) return

  const mm = gsap.matchMedia()
  gsapMatchMediaRevert = () => {
    mm.revert()
    gsapMatchMediaRevert = undefined
  }

  mm.add('(prefers-reduced-motion: no-preference)', () => {
    if (heroRef.value) {
      const tl = gsap.timeline()
      tl.from(heroRef.value.querySelectorAll('[data-gsap="hero"]'), {
        y: 60,
        opacity: 0,
        duration: 1,
        stagger: 0.18,
        ease: 'power3.out'
      })
      tl.from(heroRef.value.querySelectorAll('[data-gsap="hero-glow"]'), {
        scale: 0.5,
        opacity: 0,
        duration: 1.6,
        ease: 'power2.out'
      }, 0.1)
    }

    sectionRefs.value.forEach((el) => {
      if (!el) return
      const visual = el.querySelector('[data-gsap="visual"]')
      const text = el.querySelector('[data-gsap="text"]')
      const isReversed = el.dataset.reverse === 'true'

      if (visual) {
        gsap.from(visual, {
          x: isReversed ? 100 : -100,
          opacity: 0,
          duration: 1,
          ease: 'power3.out',
          scrollTrigger: { trigger: el, start: 'top 75%', once: true }
        })
      }
      if (text) {
        gsap.from(text, {
          x: isReversed ? -80 : 80,
          opacity: 0,
          duration: 1,
          delay: 0.1,
          ease: 'power3.out',
          scrollTrigger: { trigger: el, start: 'top 75%', once: true }
        })
      }
    })

    if (sellingRef.value) {
      gsap.from(sellingRef.value.querySelectorAll('[data-gsap="selling"]'), {
        y: 80,
        opacity: 0,
        duration: 1,
        stagger: 0.18,
        ease: 'power3.out',
        scrollTrigger: { trigger: sellingRef.value, start: 'top 75%', once: true }
      })
    }

    if (ctaRef.value) {
      gsap.from(ctaRef.value.querySelectorAll('[data-gsap="cta"]'), {
        y: 60,
        opacity: 0,
        scale: 0.96,
        duration: 0.9,
        stagger: 0.14,
        ease: 'power2.out',
        scrollTrigger: { trigger: ctaRef.value, start: 'top 80%', once: true }
      })
    }
  })
})

onBeforeUnmount(() => {
  stopFormFillLoop()
  gsapMatchMediaRevert?.()
  const { $ScrollTrigger } = useNuxtApp()
  const ScrollTrigger = $ScrollTrigger as typeof import('gsap/ScrollTrigger')['ScrollTrigger']
  ScrollTrigger.getAll().forEach(t => t.kill())
})

const steps = [
  {
    id: 'scan',
    badge: 'Étape 1',
    title: 'Scannez votre carte Pokémon',
    desc: 'Prenez une photo de votre carte Pokémon TCG. GoupixDex identifie instantanément l\'édition, la rareté, la langue et récupère les prix Cardmarket et TCGPlayer en temps réel.',
    bullets: [
      'Reconnaissance automatique via scan photo',
      'Prix Cardmarket & TCGPlayer en temps réel',
      'Détection de l\'édition, rareté et langue'
    ]
  },
  {
    id: 'form',
    badge: 'Étape 3',
    title: 'Annonce préremplie (Vinted & eBay)',
    desc: 'Titre optimisé, description détaillée, prix conseillé basé sur Cardmarket et marge : tout est calculé et prérempli selon la place de marché visée. Il ne reste plus qu\'à valider.',
    bullets: [
      'Prix basé sur les données Cardmarket',
      'Marge bénéficiaire automatiquement calculée',
      'Textes adaptés à Vinted ou aux exigences eBay'
    ]
  },
  {
    id: 'list',
    badge: 'Étape 4',
    title: 'Publication sur Vinted ou eBay',
    desc: 'En un clic, votre annonce part sur la plateforme choisie avec photos, prix et description. Fini le copier-coller entre outils et marketplaces.',
    bullets: [
      'Automatisation Vinted (navigateur) ou flux eBay (API)',
      'Photos et champs alignés avec chaque canal',
      'Une seule base article pour plusieurs canaux'
    ]
  },
  {
    id: 'stats',
    badge: 'Étape 4',
    title: 'Analytics et suivi des performances',
    desc: 'Tableau de bord complet avec chiffre d\'affaires, marges par carte, état du stock et évolution des prix Cardmarket — y compris après import depuis votre dressing Vinted.',
    bullets: [
      'Chiffre d\'affaires et marges en temps réel',
      'Suivi de l\'évolution des prix du marché',
      'Gestion du stock et historique des ventes'
    ]
  },
  {
    id: 'sale',
    badge: 'Étape 6',
    title: 'Vente confirmée, stock mis à jour',
    desc: 'Dès qu\'une vente est confirmée (Vinted ou recoupement avec votre activité), GoupixDex met à jour votre stock, calcule la marge nette et enregistre la transaction.',
    bullets: [
      'Mise à jour du stock automatique',
      'Marge nette calculée par transaction',
      'Historique complet pour votre comptabilité'
    ]
  }
]

const syncLanding = {
  badge: 'Étape 2',
  title: 'Synchronisez votre dressing Vinted',
  desc: "Importez votre collection, vos annonces en ligne et l'historique des ventes pour aligner tableau de bord, stock et marges — sans double saisie.",
  bullets: [
    'Connexion entre votre dressing Vinted et GoupixDex',
    "Vue d'ensemble : pièces, annonces actives et ventes passées",
    'Base unique pour suivre et publier ensuite sur Vinted ou eBay'
  ]
} as const

type StepDef = (typeof steps)[number]

type LandingBlock =
  | { kind: 'step'; step: StepDef }
  | { kind: 'sync' }

const landingSections = computed<LandingBlock[]>(() => {
  const out: LandingBlock[] = []
  for (const step of steps) {
    out.push({ kind: 'step', step })
    if (step.id === 'scan') {
      out.push({ kind: 'sync' })
    }
  }
  return out
})
</script>

<template>
  <div class="min-h-dvh bg-default text-default">
    <!-- Navbar -->
    <nav class="fixed top-0 z-50 w-full border-b border-default/40 bg-default/70 backdrop-blur-xl">
      <div class="mx-auto flex max-w-6xl items-center justify-between px-5 py-3 sm:px-8">
        <NuxtLink
          to="/"
          class="inline-flex items-center gap-2.5 rounded-lg px-1 py-0.5 transition-colors hover:bg-elevated/50"
        >
          <span class="flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-elevated/60 ring-1 ring-default/40">
            <img :src="logoUrl" alt="GoupixDex — cartes Pokémon TCG, Vinted et eBay" class="size-7 object-contain" width="28" height="28">
          </span>
          <span class="text-lg font-semibold tracking-tight text-highlighted">GoupixDex</span>
        </NuxtLink>

        <!-- Desktop nav -->
        <div class="hidden items-center gap-3 sm:flex">
          <span v-show="!authResolved" class="inline-flex">
            <UButton
              variant="ghost"
              color="neutral"
              size="md"
              disabled
              class="min-w-[8.75rem] justify-center pointer-events-none select-none"
              aria-busy="true"
              aria-label="Chargement de la session"
            >
              <span class="block h-4 w-[5.25rem] max-w-full rounded bg-current/15 animate-pulse" />
            </UButton>
          </span>
          <span v-show="authResolved" class="inline-flex">
            <UButton
              :to="isLoggedIn ? '/dashboard' : '/login'"
              variant="ghost"
              color="neutral"
              size="md"
            >
              {{ isLoggedIn ? 'Dashboard' : 'Connexion' }}
            </UButton>
          </span>
          <UButton
            to="/request"
            color="primary"
            size="md"
          >
            Demander l'accès
          </UButton>
        </div>

        <!-- Mobile hamburger -->
        <button
          type="button"
          class="flex size-10 items-center justify-center rounded-lg transition-colors hover:bg-elevated/60 sm:hidden"
          :aria-expanded="mobileMenuOpen"
          aria-label="Menu"
          @click="mobileMenuOpen = !mobileMenuOpen"
        >
          <UIcon :name="mobileMenuOpen ? 'i-lucide-x' : 'i-lucide-menu'" class="size-5 text-highlighted" />
        </button>
      </div>

      <!-- Mobile dropdown -->
      <Transition
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="opacity-0 -translate-y-2"
        enter-to-class="opacity-100 translate-y-0"
        leave-active-class="transition duration-150 ease-in"
        leave-from-class="opacity-100 translate-y-0"
        leave-to-class="opacity-0 -translate-y-2"
      >
        <div
          v-if="mobileMenuOpen"
          class="border-t border-default/40 bg-default/95 px-5 py-4 backdrop-blur-xl sm:hidden"
        >
          <div class="flex flex-col gap-2">
            <span v-show="!authResolved" class="flex w-full">
              <UButton
                variant="ghost"
                color="neutral"
                size="lg"
                block
                disabled
                class="pointer-events-none select-none justify-center"
                aria-busy="true"
                aria-label="Chargement de la session"
              >
                <span class="mx-auto block h-5 w-28 rounded bg-current/15 animate-pulse" />
              </UButton>
            </span>
            <span v-show="authResolved" class="flex w-full">
              <UButton
                :to="isLoggedIn ? '/dashboard' : '/login'"
                variant="ghost"
                color="neutral"
                size="lg"
                block
                @click="mobileMenuOpen = false"
              >
                {{ isLoggedIn ? 'Dashboard' : 'Connexion' }}
              </UButton>
            </span>
            <UButton
              to="/request"
              color="primary"
              size="lg"
              block
              @click="mobileMenuOpen = false"
            >
              Demander l'accès
            </UButton>
          </div>
        </div>
      </Transition>
    </nav>

    <!-- Hero -->
    <section
      ref="heroRef"
      class="relative flex min-h-[100dvh] flex-col items-center justify-center overflow-hidden px-5 pt-24 pb-20 sm:px-8"
    >
      <!-- Glow effects -->
      <div
        data-gsap="hero-glow"
        class="pointer-events-none absolute top-[-15%] left-1/2 h-[60rem] w-[60rem] -translate-x-1/2 rounded-full bg-primary/[0.09] blur-[140px]"
      />
      <div
        data-gsap="hero-glow"
        class="pointer-events-none absolute right-[-15%] bottom-[-15%] h-[35rem] w-[35rem] rounded-full bg-secondary-400/[0.07] blur-[110px]"
      />
      <div
        data-gsap="hero-glow"
        class="pointer-events-none absolute top-[20%] left-[-10%] h-[25rem] w-[25rem] rounded-full bg-primary/[0.05] blur-[90px]"
      />

      <!-- Grid pattern -->
      <div class="pointer-events-none absolute inset-0 bg-[linear-gradient(rgba(232,97,18,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(232,97,18,0.03)_1px,transparent_1px)] bg-[size:60px_60px]" />
      <div class="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,transparent_30%,var(--color-default))]" />

      <div class="relative z-10 mx-auto max-w-4xl text-center">
        <div data-gsap="hero" class="mb-8 max-sm:mb-0">
          <span class="hidden items-center gap-2.5 rounded-full border border-primary/25 bg-primary/[0.08] px-5 py-2.5 text-sm font-medium text-primary shadow-sm shadow-primary/5 backdrop-blur-sm sm:inline-flex">
            <span class="relative flex size-2">
              <span class="absolute inline-flex size-full animate-ping rounded-full bg-primary/60" />
              <span class="relative inline-flex size-2 rounded-full bg-primary" />
            </span>
            Accès limité — Places disponibles
          </span>
        </div>

        <h1
          data-gsap="hero"
          class="text-[32px] font-extrabold leading-[1.28] tracking-tight text-highlighted sm:text-4xl sm:leading-[1.1] lg:text-5xl"
        >
          Scannez vos cartes Pokémon,<br class="hidden sm:block" aria-hidden="true"><span class="sm:hidden"> </span>          <span class="bg-linear-to-r from-primary via-secondary-500 to-primary bg-[length:200%_auto] bg-clip-text text-transparent">
            mise en ligne automatisée sur Vinted &amp; eBay
          </span>
        </h1>

        <p
          data-gsap="hero"
          class="mx-auto mt-9 max-w-2xl text-base leading-relaxed text-muted sm:mt-6 sm:text-lg"
        >
          Importez votre dressing <strong class="text-highlighted">Vinted</strong> ou scannez vos cartes :
          <strong class="text-highlighted">GoupixDex</strong> automatise la récupération des prix
          <strong class="text-highlighted">Cardmarket</strong>, la génération d'annonces optimisées et la publication sur
          <strong class="text-highlighted">Vinted</strong> et <strong class="text-highlighted">eBay</strong>.
        </p>

        <div
          data-gsap="hero"
          class="mt-12 flex flex-col items-center gap-4 sm:flex-row sm:justify-center"
        >
          <UButton
            to="/request"
            color="primary"
            size="xl"
            class="px-10 py-3.5 text-base shadow-lg shadow-primary/25"
          >
            <UIcon name="i-lucide-mail" class="mr-2 size-5" />
            Demander l'accès gratuitement
          </UButton>
        </div>

        <p
          data-gsap="hero"
          class="mt-6 hidden items-center justify-center gap-4 text-sm text-muted/60 sm:flex"
        >
          <span class="flex items-center gap-1.5">
            <UIcon name="i-lucide-shield-check" class="size-4" />
            100% gratuit
          </span>
          <span class="h-3 w-px bg-muted/20" />
          <span class="flex items-center gap-1.5">
            <UIcon name="i-lucide-clock" class="size-4" />
            Réponse sous 24h
          </span>
          <span class="h-3 w-px bg-muted/20" />
          <span class="flex items-center gap-1.5">
            <UIcon name="i-lucide-lock" class="size-4" />
            Sans engagement
          </span>
        </p>
      </div>

      <!-- Scroll indicator -->
      <div data-gsap="hero" class="absolute bottom-10 left-1/2 -translate-x-1/2">
        <div class="flex flex-col items-center gap-3 text-muted/50">
          <span class="text-xs font-medium tracking-wide uppercase">Découvrir</span>
          <div class="flex h-8 w-5 items-start justify-center rounded-full border border-muted/30 p-1">
            <div class="h-2 w-1 animate-bounce rounded-full bg-primary/60" />
          </div>
        </div>
      </div>
    </section>

    <!-- Step sections (+ sync after scan) -->
    <template v-for="(block, idx) in landingSections" :key="block.kind === 'sync' ? 'landing-sync' : block.step.id">
      <section
        :ref="(el) => setSectionRef(el, idx)"
        :data-reverse="idx % 2 === 1"
        class="relative border-t border-default/40 px-5 py-20 sm:px-8 sm:py-28 lg:py-32"
        :class="idx % 2 === 0 ? 'bg-default' : 'bg-elevated/20'"
      >
        <!-- Section glows -->
        <div
          v-if="idx % 3 === 0"
          class="pointer-events-none absolute top-0 left-0 h-[25rem] w-[25rem] rounded-full bg-primary/[0.04] blur-[100px]"
        />
        <div
          v-if="idx % 3 === 2"
          class="pointer-events-none absolute right-0 bottom-0 h-[25rem] w-[25rem] rounded-full bg-secondary-400/[0.04] blur-[100px]"
        />

        <div
          class="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-2 lg:gap-20"
          :class="idx % 2 === 1 ? 'lg:[direction:rtl]' : ''"
        >
          <!-- Animation visual -->
          <div
            data-gsap="visual"
            class="flex justify-center lg:[direction:ltr]"
          >
            <div class="relative w-full max-w-sm">
              <div class="absolute -inset-3 rounded-2xl border border-default/25 sm:-inset-5" />
              <div class="absolute -inset-6 rounded-3xl border border-default/10 sm:-inset-9" />

              <div class="relative overflow-hidden rounded-xl border border-default/50 bg-elevated/70 shadow-2xl shadow-default/20 ring-1 ring-default/30">
                <div class="relative min-h-[20rem] w-full sm:min-h-[24rem]">
                  <template v-if="block.kind === 'step'">
                    <FlowScanStep
                      v-if="block.step.id === 'scan'"
                      :reduce-motion="reduceMotion"
                    />
                    <FlowFormStep
                      v-if="block.step.id === 'form'"
                      :form-fill="formFill"
                    />
                    <FlowPublishLoopStep
                      v-if="block.step.id === 'list'"
                      :reduce-motion="reduceMotion"
                    />
                    <FlowStatsStep
                      v-if="block.step.id === 'stats'"
                      :reduce-motion="reduceMotion"
                    />
                    <FlowSaleStep
                      v-if="block.step.id === 'sale'"
                      :reduce-motion="reduceMotion"
                    />
                  </template>
                  <FlowSyncStep
                    v-else
                    :reduce-motion="reduceMotion"
                  />
                </div>
              </div>
            </div>
          </div>

          <!-- Text content -->
          <div
            data-gsap="text"
            class="lg:[direction:ltr]"
          >
            <template v-if="block.kind === 'sync'">
              <span class="inline-flex items-center rounded-full bg-primary/10 px-4 py-1.5 text-xs font-semibold tracking-wide text-primary ring-1 ring-primary/20">
                {{ syncLanding.badge }}
              </span>
              <h2 class="mt-6 text-3xl font-bold tracking-tight text-highlighted sm:text-4xl">
                {{ syncLanding.title }}
              </h2>
              <p class="mt-5 max-w-lg text-base leading-relaxed text-muted sm:text-lg">
                {{ syncLanding.desc }}
              </p>
              <ul class="mt-8 space-y-4">
                <li
                  v-for="bullet in syncLanding.bullets"
                  :key="bullet"
                  class="flex items-start gap-3 text-sm text-muted sm:text-base"
                >
                  <span class="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary ring-1 ring-primary/20">
                    <UIcon name="i-lucide-check" class="size-3.5" />
                  </span>
                  {{ bullet }}
                </li>
              </ul>
            </template>
            <template v-else>
              <span class="inline-flex items-center rounded-full bg-primary/10 px-4 py-1.5 text-xs font-semibold tracking-wide text-primary ring-1 ring-primary/20">
                {{ block.step.badge }}
              </span>
              <h2 class="mt-6 text-3xl font-bold tracking-tight text-highlighted sm:text-4xl">
                {{ block.step.title }}
              </h2>
              <p class="mt-5 max-w-lg text-base leading-relaxed text-muted sm:text-lg">
                {{ block.step.desc }}
              </p>
              <ul class="mt-8 space-y-4">
                <li
                  v-for="bullet in block.step.bullets"
                  :key="bullet"
                  class="flex items-start gap-3 text-sm text-muted sm:text-base"
                >
                  <span class="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary ring-1 ring-primary/20">
                    <UIcon name="i-lucide-check" class="size-3.5" />
                  </span>
                  {{ bullet }}
                </li>
              </ul>
            </template>
          </div>
        </div>
      </section>
    </template>

    <!-- Selling card animation section -->
    <section
      ref="sellingRef"
      class="relative border-t border-default/40 bg-linear-to-b from-default via-elevated/20 to-default px-5 py-20 sm:px-8 sm:py-28 lg:py-32"
    >
      <div class="pointer-events-none absolute top-1/2 left-1/2 h-[45rem] w-[45rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary/[0.04] blur-[120px]" />

      <div class="relative mx-auto max-w-6xl">
        <div class="mb-16 text-center sm:mb-20" data-gsap="selling">
          <span class="inline-flex items-center rounded-full bg-success/10 px-4 py-1.5 text-xs font-semibold tracking-wide text-success ring-1 ring-success/20">
            Automatisation complète
          </span>
          <h2 class="mt-6 text-3xl font-bold tracking-tight text-highlighted sm:text-4xl lg:text-5xl">
            Un flux de vente continu
          </h2>
          <p class="mx-auto mt-5 max-w-2xl text-base leading-relaxed text-muted sm:text-lg">
            Du scan à la vente sur Vinted ou eBay, chaque carte suit le même fil : pricing Cardmarket,
            publication sur la marketplace choisie, puis mise à jour du stock lorsque la vente est connue.
          </p>
        </div>

        <div class="grid items-center gap-12 lg:grid-cols-2 lg:gap-20">
          <!-- Cards (left) -->
          <div data-gsap="selling">
            <div class="grid gap-5 sm:grid-cols-2">
              <div
                v-for="item in [
                  { icon: 'i-lucide-refresh-cw', title: 'Dressing Vinted à jour', desc: 'Import catalogue, annonces actives et ventes passées pour aligner GoupixDex sur votre activité réelle.' },
                  { icon: 'i-lucide-layers', title: 'Gestion du stock', desc: 'Chaque carte est suivie du scan à la vente, avec une vision unique sur Vinted et eBay.' },
                  { icon: 'i-lucide-badge-check', title: 'Marquage automatique', desc: 'État « vendu » dès que la transaction est confirmée côté Vinted ou recoupée avec vos données.' },
                  { icon: 'i-lucide-calculator', title: 'Calcul des marges', desc: 'Prix d\'achat, référence Cardmarket, frais marketplace : marge nette calculée automatiquement.' }
                ]"
                :key="item.title"
                class="rounded-xl border border-default/50 bg-elevated p-5 ring-1 ring-default/30 transition-all duration-300 hover:border-primary/30 hover:shadow-xl hover:shadow-primary/5"
              >
                <div class="mb-3 flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary ring-1 ring-primary/20">
                  <UIcon :name="item.icon" class="size-5" />
                </div>
                <h3 class="mb-1.5 text-sm font-semibold text-highlighted">{{ item.title }}</h3>
                <p class="text-sm leading-relaxed text-muted">{{ item.desc }}</p>
              </div>
            </div>
          </div>
          <!-- Animation (right) -->
          <div data-gsap="selling" class="flex justify-center">
            <div class="w-full max-w-[16rem]">
              <SellingCardAnimation />
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Bottom CTA -->
    <section
      ref="ctaRef"
      class="relative border-t border-default/40 px-5 py-24 sm:px-8 sm:py-32 lg:py-40"
    >
      <div class="pointer-events-none absolute inset-0 bg-linear-to-b from-transparent via-primary/[0.04] to-transparent" />
      <div class="pointer-events-none absolute top-1/2 left-1/2 h-[40rem] w-[40rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary/[0.07] blur-[130px]" />

      <div class="relative mx-auto max-w-3xl text-center">
        <h2 data-gsap="cta" class="text-3xl font-bold tracking-tight text-highlighted sm:text-4xl lg:text-5xl">
          Prêt à automatiser vos ventes<br>de cartes Pokémon ?
        </h2>
        <p data-gsap="cta" class="mx-auto mt-6 max-w-xl text-base leading-relaxed text-muted sm:text-lg">
          Rejoignez les premiers utilisateurs de GoupixDex et transformez votre collection TCG
          en activité pilotée : import dressing, scan, pricing Cardmarket, publications Vinted et eBay — dans un seul espace.
        </p>
        <div data-gsap="cta" class="mt-10">
          <UButton
            to="/request"
            color="primary"
            size="xl"
            class="px-10 py-3.5 text-base shadow-lg shadow-primary/25"
          >
            <UIcon name="i-lucide-mail" class="mr-2 size-5" />
            Demander l'accès gratuitement
          </UButton>
        </div>
        <p data-gsap="cta" class="mt-6 text-sm text-muted/50">
          Gratuit · Sans engagement · Réponse sous 24h
        </p>
      </div>
    </section>

    <!-- Footer -->
    <footer class="border-t border-default/40 bg-elevated/30">
      <div class="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-5 py-8 sm:flex-row sm:px-8">
        <div class="flex items-center gap-2.5">
          <img :src="logoUrl" alt="GoupixDex" class="size-6 object-contain" width="24" height="24">
          <span class="text-sm font-medium text-muted">© {{ new Date().getFullYear() }} GoupixDex</span>
        </div>
        <div class="flex items-center gap-2 text-sm text-muted">
          <UIcon name="i-lucide-shield-check" class="size-4 shrink-0 text-primary" />
          <span>Connexion sécurisée</span>
        </div>
      </div>
    </footer>
  </div>
</template>
