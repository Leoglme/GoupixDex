<template>
  <div class="grid min-h-dvh w-full grid-cols-1 grid-rows-[auto_1fr] lg:grid-cols-2 lg:grid-rows-1">
    <!-- Zone marque -->
    <aside
      class="border-default from-primary/15 via-default to-default relative flex min-w-0 flex-col gap-8 border-b bg-linear-to-br px-6 pt-8 pb-3 sm:px-10 sm:pt-10 sm:pb-4 lg:min-h-dvh lg:justify-between lg:gap-12 lg:border-e lg:border-b-0 lg:px-14 lg:py-16 lg:pb-16 xl:px-20"
    >
      <div class="space-y-10 pb-6 lg:space-y-10 lg:pb-0">
        <NuxtLink
          to="/"
          class="hover:bg-elevated/50 focus-visible:ring-primary -ms-1 inline-flex w-fit items-center gap-3.5 rounded-lg px-1 py-1 transition-colors focus-visible:ring-2 focus-visible:outline-none lg:gap-3"
        >
          <span
            class="bg-elevated/60 ring-default/40 flex size-12 shrink-0 items-center justify-center overflow-hidden rounded-lg ring-1 lg:size-11"
          >
            <img :src="logoUrl" alt="GoupixDex" class="size-10 object-contain lg:size-9" width="40" height="40" />
          </span>
          <span class="text-highlighted text-xl font-semibold tracking-tight lg:text-lg"> GoupixDex </span>
        </NuxtLink>
        <div class="space-y-5 lg:space-y-4">
          <h1 class="text-highlighted text-3xl leading-tight font-semibold tracking-tight sm:text-4xl">Bienvenue</h1>
          <p class="text-muted max-w-md text-base leading-relaxed text-pretty">
            Automatise ta collection, la mise en ligne et l'évolution des prix : il te suffit de scanner tes cartes
            Pokémon TCG.
          </p>
        </div>
      </div>

      <div class="hidden min-h-0 w-full min-w-0 shrink-0 lg:flex lg:flex-1 lg:flex-col lg:justify-center lg:py-2">
        <GoupixDexFlowAnimation class="mx-auto w-full max-w-2xl min-w-0 2xl:max-w-[50rem]" />
      </div>
    </aside>

    <!-- Zone formulaire -->
    <main
      class="bg-elevated flex min-h-0 flex-col px-6 pt-6 pb-4 sm:px-10 sm:pt-8 sm:pb-5 lg:min-h-dvh lg:px-14 lg:py-16 xl:px-20"
    >
      <div class="flex min-h-0 flex-1 flex-col justify-start pt-5 lg:justify-center lg:pt-0">
        <div class="mx-auto w-full max-w-md">
          <div class="mb-10 space-y-2">
            <h2 class="text-highlighted text-2xl font-semibold">Connexion</h2>
            <p class="text-muted text-sm">Entrez vos identifiants pour accéder à l'application.</p>
          </div>
          <GoupixDexLoginForm />
        </div>
      </div>

      <div class="mx-auto mt-8 flex w-full max-w-md shrink-0 flex-col gap-4 pb-2 sm:mt-10 sm:gap-5 sm:pb-3">
        <div class="text-muted flex items-center gap-2 text-sm">
          <UIcon name="i-lucide-shield-check" class="text-primary size-4 shrink-0" />
          <span>Connexion sécurisée à votre espace</span>
        </div>
        <p class="text-muted text-xs">© {{ new Date().getFullYear() }} GoupixDex</p>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import logoUrl from '~/assets/images/logo-goupix-dev-256x256.png'

definePageMeta({
  layout: 'auth',
  middleware: 'guest',
})

useGoupixPageSeo(
  'Connexion',
  'Connectez-vous à GoupixDex pour gérer vos articles, votre stock Pokémon TCG et vos publications.',
)
</script>
