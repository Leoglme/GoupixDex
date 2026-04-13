<script setup lang="ts">
import logoUrl from '~/assets/images/logo-goupix-dev-256x256.png'

definePageMeta({
  layout: 'auth',
  middleware: 'guest'
})
</script>

<template>
  <div
    class="grid min-h-dvh w-full grid-cols-1 grid-rows-[auto_1fr] lg:grid-cols-2 lg:grid-rows-1"
  >
    <!-- Zone marque -->
    <aside
      class="relative flex flex-col gap-8 border-b border-default bg-linear-to-br from-primary/15 via-default to-default px-6 pt-8 pb-3 sm:px-10 sm:pt-10 sm:pb-4 lg:min-h-dvh lg:justify-between lg:gap-12 lg:border-e lg:border-b-0 lg:px-14 lg:py-16 lg:pb-16 xl:px-20"
    >
      <div class="space-y-8 lg:space-y-10">
        <NuxtLink
          to="/"
          class="inline-flex w-fit items-center gap-3 rounded-lg px-1 py-1 -ms-1 transition-colors hover:bg-elevated/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <span
            class="flex size-11 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-elevated/60 ring-1 ring-default/40"
          >
            <img
              :src="logoUrl"
              alt="GoupixDex"
              class="size-9 object-contain"
              width="36"
              height="36"
            >
          </span>
          <span class="text-lg font-semibold tracking-tight text-highlighted">
            GoupixDex
          </span>
        </NuxtLink>
        <div class="space-y-4">
          <h1 class="text-3xl font-semibold leading-tight tracking-tight text-highlighted sm:text-4xl">
            Bienvenue
          </h1>
          <p class="max-w-md text-pretty text-base leading-relaxed text-muted">
            Gestion de stock Pokémon TCG, marges et suivi des ventes Vinted — tout depuis un seul tableau de bord.
          </p>
        </div>
      </div>

      <div class="hidden gap-6 lg:flex lg:flex-col">
        <div class="flex items-center gap-2 text-sm text-muted">
          <UIcon
            name="i-lucide-shield-check"
            class="size-4 shrink-0 text-primary"
          />
          <span>Connexion sécurisée à votre espace</span>
        </div>
        <p class="text-xs text-muted">
          © {{ new Date().getFullYear() }} GoupixDex
        </p>
      </div>
    </aside>

    <!-- Zone formulaire -->
    <main
      class="flex min-h-0 flex-col bg-elevated px-6 pt-6 pb-4 sm:px-10 sm:pt-8 sm:pb-5 lg:min-h-dvh lg:px-14 lg:py-16 xl:px-20"
    >
      <div class="flex min-h-0 flex-1 flex-col justify-center">
        <div class="mx-auto w-full max-w-md">
          <div class="mb-10 space-y-2">
            <h2 class="text-2xl font-semibold text-highlighted">
              Connexion
            </h2>
            <p class="text-sm text-muted">
              Entrez vos identifiants pour accéder à l’application.
            </p>
          </div>
          <LoginForm />
        </div>
      </div>

      <div class="mx-auto mt-6 w-full max-w-md flex flex-col gap-6 lg:hidden">
        <div class="flex items-center gap-2 text-sm text-muted">
          <UIcon
            name="i-lucide-shield-check"
            class="size-4 shrink-0 text-primary"
          />
          <span>Connexion sécurisée à votre espace</span>
        </div>
        <p class="text-xs text-muted">
          © {{ new Date().getFullYear() }} GoupixDex
        </p>
      </div>
    </main>
  </div>
</template>
