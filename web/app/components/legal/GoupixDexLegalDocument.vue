<template>
  <div
    class="mx-auto grid max-w-6xl gap-8 px-5 pt-28 pb-20 sm:px-8 sm:pt-32 lg:grid-cols-[15rem_minmax(0,1fr)] lg:gap-16 lg:pt-40 lg:pb-28"
  >
    <aside class="grid min-w-0 content-start gap-4 lg:sticky lg:top-28 lg:gap-6 lg:self-start">
      <p class="app-label">Informations légales</p>
      <nav
        aria-label="Informations légales"
        class="-mx-5 flex gap-2 overflow-x-auto px-5 pb-1 [scrollbar-width:none] sm:-mx-8 sm:px-8 lg:mx-0 lg:flex-col lg:gap-0 lg:overflow-visible lg:px-0 lg:pb-0"
      >
        <NuxtLink
          v-for="legalDocument in LEGAL_DOCUMENTS"
          :key="legalDocument.id"
          :to="legalDocument.path"
          :aria-current="legalDocument.id === props.documentId ? 'page' : undefined"
          class="shrink-0 rounded-full border px-4 py-2 text-sm font-semibold whitespace-nowrap transition-colors lg:rounded-none lg:border-0 lg:border-l-2 lg:px-0 lg:py-2.5 lg:pl-4 lg:whitespace-normal"
          :class="
            legalDocument.id === props.documentId
              ? 'border-(--app-accent) bg-(--app-accent-soft) text-(--app-accent-ink) lg:border-(--app-accent) lg:bg-transparent lg:text-(--app-ink)'
              : 'text-muted border-(--app-line) bg-(--app-surface) hover:text-(--app-ink) lg:border-(--app-line) lg:bg-transparent'
          "
        >
          {{ legalDocument.label }}
        </NuxtLink>
      </nav>
      <div class="app-card hidden content-start gap-1.5 p-4 text-sm lg:grid">
        <p class="app-label mb-1">Une question ?</p>
        <a
          :href="PUBLISHER.emailHref"
          class="text-highlighted justify-self-start font-semibold hover:text-(--app-accent)"
        >
          {{ PUBLISHER.email }}
        </a>
        <a
          :href="PUBLISHER.phoneHref"
          class="text-highlighted justify-self-start font-semibold tabular-nums hover:text-(--app-accent)"
        >
          {{ PUBLISHER.phone }}
        </a>
        <NuxtLink to="/contact" class="landing-link mt-2 justify-self-start">Page contact</NuxtLink>
      </div>
    </aside>

    <article class="max-w-3xl min-w-0 [counter-reset:legal-section]">
      <p class="landing-eyebrow">{{ LEGAL_LAST_UPDATE_LABEL }}</p>
      <h1
        class="font-display text-highlighted mt-6 text-4xl leading-[1.08] font-semibold tracking-[-0.01em] sm:text-5xl"
      >
        {{ props.title }}<span class="text-(--app-accent)" aria-hidden="true">.</span>
      </h1>
      <p class="text-muted mt-6 max-w-2xl text-lg leading-relaxed">{{ props.intro }}</p>
      <slot />
    </article>
  </div>
</template>

<script lang="ts" setup>
import type { PropType } from 'vue'
import type { GoupixDexLegalDocumentProps, LegalDocumentId, LegalDocumentLink } from '~/types/GoupixDexLegalDocument'
import { PUBLISHER } from '~/utils/publisher'

const props: GoupixDexLegalDocumentProps = defineProps({
  documentId: {
    type: String as PropType<LegalDocumentId>,
    required: true,
  },
  title: {
    type: String,
    required: true,
  },
  intro: {
    type: String,
    required: true,
  },
})

const LEGAL_DOCUMENTS: LegalDocumentLink[] = [
  { id: 'legal', path: '/legal', label: 'Mentions légales' },
  { id: 'privacy', path: '/privacy', label: 'Politique de confidentialité' },
  { id: 'terms', path: '/terms', label: "Conditions d'utilisation" },
]
const LEGAL_LAST_UPDATE_LABEL: string = 'Dernière mise à jour : 1er octobre 2026'
</script>
