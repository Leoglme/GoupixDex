<template>
  <div class="min-h-dvh bg-(--app-bg) text-(--app-ink)">
    <!-- Navbar -->
    <nav class="fixed top-0 z-50 w-full border-b border-(--app-line) bg-(--app-surface)/80 backdrop-blur-xl">
      <div class="mx-auto flex max-w-6xl items-center justify-between px-5 py-3 sm:px-8">
        <NuxtLink to="/" class="flex items-center gap-2.5 rounded-lg px-1 py-0.5 transition-opacity hover:opacity-80">
          <img
            :src="logoUrl"
            alt="GoupixDex — cartes Pokémon TCG, Vinted et eBay"
            class="size-8 object-contain"
            width="32"
            height="32"
          />
          <span class="font-display text-highlighted text-lg font-semibold">GoupixDex</span>
        </NuxtLink>

        <!-- Desktop nav -->
        <div class="hidden items-center gap-2 sm:flex">
          <UButton variant="ghost" color="neutral" size="md" @click="scrollToSection('#comment-ca-marche')">
            Comment ça marche
          </UButton>
          <span v-show="!authResolved" class="inline-flex">
            <UButton
              variant="ghost"
              color="neutral"
              size="md"
              disabled
              class="pointer-events-none min-w-[8.75rem] justify-center select-none"
              aria-busy="true"
              aria-label="Chargement de la session"
            >
              <span class="block h-4 w-[5.25rem] max-w-full animate-pulse rounded bg-current/15" />
            </UButton>
          </span>
          <span v-show="authResolved" class="inline-flex">
            <UButton :to="isLoggedIn ? '/dashboard' : '/login'" variant="ghost" color="neutral" size="md">
              {{ isLoggedIn ? 'Dashboard' : 'Connexion' }}
            </UButton>
          </span>
          <UButton to="/request" color="primary" size="md" class="px-5"> Demander l'accès </UButton>
        </div>

        <!-- Mobile hamburger -->
        <button
          type="button"
          class="flex size-10 items-center justify-center rounded-lg transition-colors hover:bg-(--app-surface-2) sm:hidden"
          :aria-expanded="mobileMenuOpen"
          aria-label="Menu"
          @click="mobileMenuOpen = !mobileMenuOpen"
        >
          <UIcon :name="mobileMenuOpen ? 'i-lucide-x' : 'i-lucide-menu'" class="text-highlighted size-5" />
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
          class="border-t border-(--app-line) bg-(--app-surface)/95 px-5 py-4 backdrop-blur-xl sm:hidden"
        >
          <div class="flex flex-col gap-2">
            <span v-show="!authResolved" class="flex w-full">
              <UButton
                variant="ghost"
                color="neutral"
                size="lg"
                block
                disabled
                class="pointer-events-none justify-center select-none"
                aria-busy="true"
                aria-label="Chargement de la session"
              >
                <span class="mx-auto block h-5 w-28 animate-pulse rounded bg-current/15" />
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
            <UButton to="/request" color="primary" size="lg" block @click="mobileMenuOpen = false">
              Demander l'accès
            </UButton>
          </div>
        </div>
      </Transition>
    </nav>

    <!-- Hero -->
    <section class="relative overflow-hidden">
      <div
        class="mx-auto grid max-w-6xl items-center gap-12 px-5 pt-32 pb-16 sm:px-8 lg:grid-cols-[1.15fr_0.85fr] lg:gap-16 lg:pt-40 lg:pb-24"
      >
        <div>
          <p class="landing-eyebrow landing-rise" :style="{ animationDelay: '0ms' }">L'atelier du vendeur Pokémon</p>

          <h1
            class="landing-rise font-display text-highlighted mt-6 max-w-2xl text-4xl leading-[1.08] font-semibold tracking-[-0.01em] sm:text-5xl lg:text-6xl"
            :style="{ animationDelay: '90ms' }"
          >
            Vos cartes Pokémon, de la photo à la vente<span class="text-(--app-accent)" aria-hidden="true">.</span>
          </h1>

          <p class="landing-rise text-muted mt-6 max-w-xl text-lg leading-relaxed" :style="{ animationDelay: '180ms' }">
            GoupixDex lit vos cartes au scan, récupère les prix Cardmarket, rédige l'annonce et la publie sur
            <strong class="text-highlighted">Vinted</strong> et <strong class="text-highlighted">eBay</strong>. Vous
            gardez la main — il fait le reste.
          </p>

          <div
            class="landing-rise mt-9 flex flex-col items-stretch gap-3 sm:flex-row sm:items-center"
            :style="{ animationDelay: '270ms' }"
          >
            <UButton to="/request" color="primary" size="xl" class="justify-center px-8">
              Demander l'accès
              <UIcon name="i-lucide-arrow-right" class="size-4" />
            </UButton>
            <UButton
              color="neutral"
              variant="outline"
              size="xl"
              class="justify-center px-8"
              @click="scrollToSection('#comment-ca-marche')"
            >
              Voir comment ça marche
            </UButton>
          </div>

          <ul
            class="landing-rise mt-8 flex flex-wrap items-center gap-x-6 gap-y-2"
            :style="{ animationDelay: '360ms' }"
          >
            <li
              v-for="marker in trustMarkers"
              :key="marker"
              class="text-muted inline-flex items-center gap-2 font-mono text-xs tracking-wide uppercase"
            >
              <UIcon name="i-lucide-check" class="size-3.5 text-(--app-accent)" />
              {{ marker }}
            </li>
          </ul>
        </div>

        <div class="landing-rise hidden justify-center lg:flex" :style="{ animationDelay: '300ms' }">
          <div class="w-full max-w-[15rem]">
            <GoupixDexSellingCardAnimation />
          </div>
        </div>
      </div>
    </section>

    <!-- Step sections (+ sync after scan) -->
    <div id="comment-ca-marche" class="mx-auto max-w-6xl px-5 pt-4 sm:px-8">
      <p class="landing-eyebrow">Comment ça marche</p>
      <h2 class="font-display text-highlighted mt-4 max-w-2xl text-3xl font-semibold tracking-[-0.01em] sm:text-4xl">
        Six étapes, zéro copier-coller
      </h2>
    </div>

    <template v-for="(block, idx) in landingSections" :key="block.kind === 'sync' ? 'landing-sync' : block.step.id">
      <section
        :ref="(el) => setSectionRef(el, idx)"
        :data-reverse="idx % 2 === 1"
        class="relative px-5 py-14 sm:px-8 sm:py-20"
      >
        <div
          class="mx-auto grid max-w-6xl items-center gap-10 lg:grid-cols-2 lg:gap-20"
          :class="idx % 2 === 1 ? 'lg:[direction:rtl]' : ''"
        >
          <!-- Animation visual -->
          <div data-gsap="visual" class="flex justify-center lg:[direction:ltr]">
            <div class="app-card w-full max-w-sm overflow-hidden shadow-(--app-shadow-soft)">
              <div class="relative min-h-[20rem] w-full sm:min-h-[24rem]">
                <template v-if="block.kind === 'step'">
                  <GoupixDexFlowScanStep v-if="block.step.id === 'scan'" :reduce-motion="reduceMotion" />
                  <GoupixDexFlowFormStep v-if="block.step.id === 'form'" :form-fill="formFill" />
                  <GoupixDexFlowPublishLoopStep v-if="block.step.id === 'list'" :reduce-motion="reduceMotion" />
                  <GoupixDexFlowStatsStep v-if="block.step.id === 'stats'" :reduce-motion="reduceMotion" />
                  <GoupixDexFlowSaleStep v-if="block.step.id === 'sale'" :reduce-motion="reduceMotion" />
                </template>
                <GoupixDexFlowSyncStep v-else :reduce-motion="reduceMotion" />
              </div>
            </div>
          </div>

          <!-- Text content -->
          <div data-gsap="text" class="lg:[direction:ltr]">
            <p class="landing-eyebrow">Étape {{ String(idx + 1).padStart(2, '0') }}</p>
            <h3 class="font-display text-highlighted mt-4 text-2xl font-semibold tracking-[-0.01em] sm:text-3xl">
              {{ blockContent(block).title }}
            </h3>
            <p class="text-muted mt-4 max-w-lg text-base leading-relaxed sm:text-lg">
              {{ blockContent(block).desc }}
            </p>
            <ul class="mt-6 space-y-3">
              <li
                v-for="bullet in blockContent(block).bullets"
                :key="bullet"
                class="text-muted flex items-start gap-3 text-sm sm:text-base"
              >
                <UIcon name="i-lucide-check" class="mt-1 size-4 shrink-0 text-(--app-accent)" />
                {{ bullet }}
              </li>
            </ul>
          </div>
        </div>
      </section>
    </template>

    <!-- Feature grid -->
    <section ref="sellingRef" class="border-t border-(--app-line) bg-(--app-surface) px-5 py-16 sm:px-8 sm:py-24">
      <div class="mx-auto max-w-6xl">
        <div data-gsap="selling">
          <p class="landing-eyebrow">Au quotidien</p>
          <h2
            class="font-display text-highlighted mt-4 max-w-2xl text-3xl font-semibold tracking-[-0.01em] sm:text-4xl"
          >
            Un seul endroit pour tout votre stock
          </h2>
          <p class="text-muted mt-4 max-w-2xl text-base leading-relaxed sm:text-lg">
            Du scan à la vente, chaque carte suit le même fil : pricing Cardmarket, publication sur la marketplace
            choisie, puis mise à jour du stock dès que la vente est connue.
          </p>
        </div>

        <div data-gsap="selling" class="mt-10 grid gap-4 sm:grid-cols-2">
          <div
            v-for="item in featureCards"
            :key="item.title"
            class="app-card p-5 transition-colors hover:border-(--app-ink-soft)"
          >
            <div class="app-icon-tile mb-4">
              <UIcon :name="item.icon" class="size-5 text-(--app-accent)" />
            </div>
            <h3 class="text-highlighted mb-1.5 text-sm font-semibold">{{ item.title }}</h3>
            <p class="text-muted text-sm leading-relaxed">{{ item.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Bottom CTA -->
    <section ref="ctaRef" class="border-t border-(--app-line) px-5 py-20 sm:px-8 sm:py-28">
      <div class="mx-auto max-w-3xl text-center">
        <p data-gsap="cta" class="landing-eyebrow justify-center">Accès limité — places disponibles</p>
        <h2
          data-gsap="cta"
          class="font-display text-highlighted mt-5 text-3xl font-semibold tracking-[-0.01em] sm:text-4xl lg:text-5xl"
        >
          Prêt à vendre vos cartes sans y passer vos soirées<span class="text-(--app-accent)" aria-hidden="true"
            >&nbsp;?</span
          >
        </h2>
        <p data-gsap="cta" class="text-muted mx-auto mt-5 max-w-xl text-base leading-relaxed sm:text-lg">
          Import du dressing Vinted, scan, pricing Cardmarket, publications Vinted et eBay — dans un seul espace.
        </p>
        <div data-gsap="cta" class="mt-9">
          <UButton to="/request" color="primary" size="xl" class="px-9">
            Demander l'accès gratuitement
            <UIcon name="i-lucide-arrow-right" class="size-4" />
          </UButton>
        </div>
        <p data-gsap="cta" class="text-muted mt-6 font-mono text-xs tracking-wide uppercase">
          Gratuit · Sans engagement · Réponse sous 24 h
        </p>
      </div>
    </section>

    <!-- Footer -->
    <footer class="border-t border-(--app-line) bg-(--app-surface)">
      <div class="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-5 py-8 sm:flex-row sm:px-8">
        <div class="flex items-center gap-2.5">
          <img :src="logoUrl" alt="GoupixDex" class="size-6 object-contain" width="24" height="24" />
          <span class="text-muted text-sm font-medium">© {{ new Date().getFullYear() }} GoupixDex</span>
        </div>
        <div class="text-muted flex items-center gap-5 text-sm">
          <NuxtLink to="/privacy" class="transition-colors hover:text-(--app-ink)">Confidentialité</NuxtLink>
          <NuxtLink to="/request" class="transition-colors hover:text-(--app-ink)">Demander l'accès</NuxtLink>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import type { ComputedRef, Ref } from 'vue'
import logoUrl from '~/assets/images/logo-goupix-dev-256x256.png'

definePageMeta({
  layout: 'auth',
})

useGoupixPageSeo(
  'Scannez vos cartes Pokémon — mise en ligne automatisée sur Vinted et eBay | GoupixDex',
  'Scan photo, prix Cardmarket & TCGPlayer, annonces générées et publication sur Vinted et eBay. Synchronisez aussi votre dressing Vinted (collection, annonces en ligne, ventes) dans votre espace. Tableau de bord et marges.',
)

useSeoMeta({
  keywords:
    'pokémon tcg, vinted, synchronisation dressing vinted, ebay, automatisation, cardmarket, tcgplayer, vente cartes pokémon, scan carte pokémon, annonce vinted, annonce ebay, goupixdex',
})

const { isLoggedIn, authResolved } = useAuth()

const reduceMotion: Ref<boolean> = ref(false)
const formFill: Ref<number> = ref(0)
const mobileMenuOpen: Ref<boolean> = ref(false)
const sectionRefs: Ref<(HTMLElement | undefined)[]> = ref([])
const sellingRef: Ref<HTMLElement | undefined> = ref(undefined)
const ctaRef: Ref<HTMLElement | undefined> = ref(undefined)

/** Trust markers under the hero CTAs. */
const trustMarkers: string[] = ['100 % gratuit', 'Réponse sous 24 h', 'Sans engagement']

/** Feature grid cards of the "Au quotidien" section. */
const featureCards: Array<{ icon: string; title: string; desc: string }> = [
  {
    icon: 'i-lucide-refresh-cw',
    title: 'Dressing Vinted à jour',
    desc: 'Import catalogue, annonces actives et ventes passées pour aligner GoupixDex sur votre activité réelle.',
  },
  {
    icon: 'i-lucide-layers',
    title: 'Gestion du stock',
    desc: 'Chaque carte est suivie du scan à la vente, avec une vision unique sur Vinted et eBay.',
  },
  {
    icon: 'i-lucide-badge-check',
    title: 'Marquage automatique',
    desc: 'État « vendu » dès que la transaction est confirmée côté Vinted ou recoupée avec vos données.',
  },
  {
    icon: 'i-lucide-calculator',
    title: 'Calcul des marges',
    desc: "Prix d'achat, référence Cardmarket, frais marketplace : marge nette calculée automatiquement.",
  },
]

let formFillTimers: ReturnType<typeof setTimeout>[] = []
let gsapMatchMediaRevert: (() => void) | undefined

/**
 * Store a step section element for the GSAP scroll animations.
 * @param el - Section root element.
 * @param idx - Section index.
 */
function setSectionRef(el: Element | null, idx: number): void {
  if (el) {
    sectionRefs.value[idx] = el as HTMLElement
  }
}

/**
 * Smooth-scroll to a section, accounting for the sticky navbar height.
 * @param selector - CSS selector of the target section.
 */
function scrollToSection(selector: string): void {
  const element: Element | null = document.querySelector(selector)
  if (element) {
    const headerOffset: number = 80
    const elementPosition: number = element.getBoundingClientRect().top
    window.scrollTo({ top: elementPosition + window.pageYOffset - headerOffset, behavior: 'smooth' })
  }
  mobileMenuOpen.value = false
}

/**
 * Loop the fake form-fill progression of the "form" step animation.
 */
function startFormFillLoop(): void {
  stopFormFillLoop()
  if (reduceMotion.value) {
    formFill.value = 4
    return
  }
  function cycle(): void {
    formFill.value = 0
    formFillTimers.push(
      setTimeout(() => {
        formFill.value = 1
      }, 400),
    )
    formFillTimers.push(
      setTimeout(() => {
        formFill.value = 2
      }, 900),
    )
    formFillTimers.push(
      setTimeout(() => {
        formFill.value = 3
      }, 1500),
    )
    formFillTimers.push(
      setTimeout(() => {
        formFill.value = 4
      }, 2200),
    )
    formFillTimers.push(setTimeout(cycle, 4500))
  }
  cycle()
}

/**
 * Clear the pending form-fill timers.
 */
function stopFormFillLoop(): void {
  formFillTimers.forEach((id) => clearTimeout(id))
  formFillTimers = []
}

onMounted(() => {
  if (!import.meta.client) return

  const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
  reduceMotion.value = mq.matches
  mq.addEventListener('change', (e) => {
    reduceMotion.value = e.matches
  })

  startFormFillLoop()

  const { $gsap } = useNuxtApp()
  const gsap = $gsap as (typeof import('gsap'))['gsap']

  if (reduceMotion.value) return

  const mm = gsap.matchMedia()
  gsapMatchMediaRevert = () => {
    mm.revert()
    gsapMatchMediaRevert = undefined
  }

  mm.add('(prefers-reduced-motion: no-preference)', () => {
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
          scrollTrigger: { trigger: el, start: 'top 75%', once: true },
        })
      }
      if (text) {
        gsap.from(text, {
          x: isReversed ? -80 : 80,
          opacity: 0,
          duration: 1,
          delay: 0.1,
          ease: 'power3.out',
          scrollTrigger: { trigger: el, start: 'top 75%', once: true },
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
        scrollTrigger: { trigger: sellingRef.value, start: 'top 75%', once: true },
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
        scrollTrigger: { trigger: ctaRef.value, start: 'top 80%', once: true },
      })
    }
  })
})

onBeforeUnmount(() => {
  stopFormFillLoop()
  gsapMatchMediaRevert?.()
  const { $ScrollTrigger } = useNuxtApp()
  const ScrollTrigger = $ScrollTrigger as (typeof import('gsap/ScrollTrigger'))['ScrollTrigger']
  ScrollTrigger.getAll().forEach((t) => t.kill())
})

const steps = [
  {
    id: 'scan',
    title: 'Scannez votre carte Pokémon',
    desc: "Prenez une photo de votre carte Pokémon TCG. GoupixDex identifie instantanément l'édition, la rareté, la langue et récupère les prix Cardmarket et TCGPlayer en temps réel.",
    bullets: [
      'Reconnaissance automatique via scan photo',
      'Prix Cardmarket & TCGPlayer en temps réel',
      "Détection de l'édition, rareté et langue",
    ],
  },
  {
    id: 'form',
    title: 'Annonce préremplie (Vinted & eBay)',
    desc: "Titre optimisé, description détaillée, prix conseillé basé sur Cardmarket et marge : tout est calculé et prérempli selon la place de marché visée. Il ne reste plus qu'à valider.",
    bullets: [
      'Prix basé sur les données Cardmarket',
      'Marge bénéficiaire automatiquement calculée',
      'Textes adaptés à Vinted ou aux exigences eBay',
    ],
  },
  {
    id: 'list',
    title: 'Publication sur Vinted ou eBay',
    desc: 'En un clic, votre annonce part sur la plateforme choisie avec photos, prix et description. Fini le copier-coller entre outils et marketplaces.',
    bullets: [
      'Automatisation Vinted (navigateur) ou flux eBay (API)',
      'Photos et champs alignés avec chaque canal',
      'Une seule base article pour plusieurs canaux',
    ],
  },
  {
    id: 'stats',
    title: 'Analytics et suivi des performances',
    desc: "Tableau de bord complet avec chiffre d'affaires, marges par carte, état du stock et évolution des prix Cardmarket — y compris après import depuis votre dressing Vinted.",
    bullets: [
      "Chiffre d'affaires et marges en temps réel",
      "Suivi de l'évolution des prix du marché",
      'Gestion du stock et historique des ventes',
    ],
  },
  {
    id: 'sale',
    title: 'Vente confirmée, stock mis à jour',
    desc: "Dès qu'une vente est confirmée (Vinted ou recoupement avec votre activité), GoupixDex met à jour votre stock, calcule la marge nette et enregistre la transaction.",
    bullets: [
      'Mise à jour du stock automatique',
      'Marge nette calculée par transaction',
      'Historique complet pour votre comptabilité',
    ],
  },
]

const syncLanding = {
  title: 'Synchronisez votre dressing Vinted',
  desc: "Importez votre collection, vos annonces en ligne et l'historique des ventes pour aligner tableau de bord, stock et marges — sans double saisie.",
  bullets: [
    'Connexion entre votre dressing Vinted et GoupixDex',
    "Vue d'ensemble : pièces, annonces actives et ventes passées",
    'Base unique pour suivre et publier ensuite sur Vinted ou eBay',
  ],
} as const

type StepDef = (typeof steps)[number]

type LandingBlock = { kind: 'step'; step: StepDef } | { kind: 'sync' }

type LandingBlockContent = { title: string; desc: string; bullets: readonly string[] }

const landingSections: ComputedRef<LandingBlock[]> = computed(() => {
  const out: LandingBlock[] = []
  for (const step of steps) {
    out.push({ kind: 'step', step })
    if (step.id === 'scan') {
      out.push({ kind: 'sync' })
    }
  }
  return out
})

/**
 * Title / description / bullets of a landing block (step or Vinted sync).
 * @param block - Landing block to render.
 * @returns The displayable content of the block.
 */
function blockContent(block: LandingBlock): LandingBlockContent {
  return block.kind === 'sync' ? syncLanding : block.step
}
</script>
