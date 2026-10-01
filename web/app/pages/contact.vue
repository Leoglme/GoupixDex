<template>
  <div>
    <section class="mx-auto max-w-6xl px-5 pt-32 sm:px-8 lg:pt-40">
      <p class="landing-eyebrow landing-rise">Contact</p>
      <h1
        class="landing-rise font-display text-highlighted mt-6 max-w-3xl text-4xl leading-[1.08] font-semibold tracking-[-0.01em] [animation-delay:90ms] sm:text-5xl lg:text-6xl"
      >
        Une question sur GoupixDex<span class="text-(--app-accent)" aria-hidden="true">&nbsp;?</span>
      </h1>
      <p class="landing-rise text-muted mt-6 max-w-xl text-lg leading-relaxed [animation-delay:180ms]">
        Je développe GoupixDex et je réponds moi-même à chaque message : une question avant de demander l'accès, un
        souci dans l'app ou une idée pour vendre vos cartes. Réponse sous 24 h en semaine.
      </p>
    </section>

    <section
      class="landing-rise mx-auto grid max-w-6xl gap-10 px-5 pt-10 pb-16 [animation-delay:270ms] sm:px-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:gap-14 lg:pt-14 lg:pb-24"
    >
      <GoupixDexContactChannels />
      <GoupixDexContactForm />
    </section>

    <section class="border-t border-(--app-line) bg-(--app-surface) py-14 sm:py-16">
      <div class="mx-auto max-w-6xl px-5 sm:px-8">
        <p class="landing-eyebrow">Avant d'écrire</p>
        <ul class="mt-6 grid gap-3 sm:grid-cols-3">
          <li v-for="shortcut in CONTACT_SHORTCUTS" :key="shortcut.to">
            <NuxtLink
              :to="shortcut.to"
              class="app-card flex h-full items-start gap-4 p-5 transition-colors hover:border-(--app-ink-soft)"
            >
              <span class="app-icon-tile">
                <UIcon :name="shortcut.icon" class="size-5 text-(--app-accent)" aria-hidden="true" />
              </span>
              <span class="min-w-0">
                <span class="text-highlighted block text-sm font-semibold">{{ shortcut.title }}</span>
                <span class="text-muted mt-1 block text-sm leading-relaxed">{{ shortcut.description }}</span>
              </span>
            </NuxtLink>
          </li>
        </ul>
      </div>
    </section>
  </div>
</template>

<script lang="ts" setup>
import { CONTACT_SHORTCUTS } from '~/utils/contactPage'

definePageMeta({
  layout: 'landing',
})

useGoupixPageSeo(
  'Contact',
  'Une question sur GoupixDex ? Écrivez à Léo ou appelez le 06 42 19 38 12 : réponse sous 24 h en semaine.',
)
</script>
