<script setup lang="ts">
import logoUrl from '~/assets/images/logo-goupix-dev-256x256.png'

definePageMeta({
  layout: 'auth'
})

const email = ref('')
const message = ref('')
const submitted = ref(false)
const loading = ref(false)

async function handleSubmit() {
  if (!email.value) return
  loading.value = true
  await new Promise(r => setTimeout(r, 1200))
  loading.value = false
  submitted.value = true
}
</script>

<template>
  <div
    class="grid min-h-dvh w-full grid-cols-1 grid-rows-[auto_1fr] lg:grid-cols-2 lg:grid-rows-1"
  >
    <!-- Zone marque -->
    <aside
      class="relative flex min-w-0 flex-col gap-8 border-b border-default bg-linear-to-br from-primary/15 via-default to-default px-6 pt-8 pb-6 sm:px-10 sm:pt-10 sm:pb-8 lg:min-h-dvh lg:justify-between lg:gap-12 lg:border-e lg:border-b-0 lg:px-14 lg:py-16 lg:pb-16 xl:px-20"
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
            Rejoignez les premiers utilisateurs
          </h1>
          <p class="max-w-md text-pretty text-base leading-relaxed text-muted">
            GoupixDex est en accès limité. Laissez vos coordonnées et soyez parmi les premiers à automatiser vos ventes de cartes Pokémon TCG sur Vinted.
          </p>
        </div>
      </div>

      <!-- Animation visible uniquement en desktop -->
      <div
        class="hidden min-h-0 w-full min-w-0 shrink-0 lg:flex lg:flex-1 lg:flex-col lg:items-center lg:justify-center lg:py-2"
      >
        <div class="w-full max-w-[14rem]">
          <SellingCardAnimation />
        </div>
      </div>

      <div class="hidden shrink-0 lg:block">
        <div class="flex items-center gap-2 text-sm text-muted">
          <UIcon
            name="i-lucide-users"
            class="size-4 shrink-0 text-primary"
          />
          <span>Places limitées · Réponse sous 24h</span>
        </div>
      </div>
    </aside>

    <!-- Zone formulaire -->
    <main
      class="flex min-h-0 flex-col bg-elevated px-6 pt-6 pb-4 sm:px-10 sm:pt-8 sm:pb-5 lg:min-h-dvh lg:px-14 lg:py-16 xl:px-20"
    >
      <div class="flex min-h-0 flex-1 flex-col justify-start pt-3 lg:justify-center lg:pt-0">
        <div class="mx-auto w-full max-w-md">
          <!-- Success state -->
          <div v-if="submitted">
            <div class="mb-10 space-y-5 text-center">
              <div class="mx-auto flex size-16 items-center justify-center rounded-full bg-success/15 text-success ring-2 ring-success/30">
                <UIcon name="i-lucide-check" class="size-8" />
              </div>
              <h2 class="text-2xl font-semibold text-highlighted sm:text-3xl">
                Demande envoyée !
              </h2>
              <p class="mx-auto max-w-sm text-base leading-relaxed text-muted">
                Merci pour votre intérêt. Nous vous recontacterons à
                <strong class="text-highlighted">{{ email }}</strong>
                dès qu'une place se libère.
              </p>
            </div>
            <div class="flex flex-col gap-3">
              <UButton
                to="/"
                variant="outline"
                color="neutral"
                size="lg"
                block
              >
                <UIcon name="i-lucide-arrow-left" class="mr-2 size-4" />
                Retour à l'accueil
              </UButton>
            </div>
          </div>

          <!-- Form state -->
          <template v-else>
            <div class="mb-10 space-y-2">
              <div class="mb-4 flex items-center gap-2">
                <NuxtLink
                  to="/"
                  class="flex size-8 items-center justify-center rounded-lg text-muted transition-colors hover:bg-default hover:text-highlighted"
                >
                  <UIcon name="i-lucide-arrow-left" class="size-4" />
                </NuxtLink>
              </div>
              <h2 class="text-2xl font-semibold text-highlighted">
                Demander l'accès
              </h2>
              <p class="text-sm text-muted">
                Remplissez le formulaire ci-dessous, nous reviendrons vers vous rapidement.
              </p>
            </div>

            <form class="space-y-5" @submit.prevent="handleSubmit">
              <UFormField label="Adresse email" required>
                <UInput
                  v-model="email"
                  type="email"
                  placeholder="vous@exemple.com"
                  icon="i-lucide-at-sign"
                  size="xl"
                  required
                  class="w-full"
                />
              </UFormField>

              <UFormField label="Message (optionnel)">
                <UTextarea
                  v-model="message"
                  placeholder="Présentez-vous ou dites-nous ce qui vous intéresse…"
                  :rows="4"
                  size="xl"
                  class="w-full"
                />
              </UFormField>

              <UButton
                type="submit"
                color="primary"
                size="xl"
                block
                :loading="loading"
                :disabled="!email || loading"
                class="mt-2"
              >
                <UIcon v-if="!loading" name="i-lucide-send" class="mr-2 size-5" />
                Envoyer ma demande
              </UButton>
            </form>

            <p class="mt-6 text-center text-xs text-muted">
              Votre email ne sera utilisé que pour vous contacter au sujet de GoupixDex.
            </p>
          </template>
        </div>
      </div>

      <div class="mx-auto mt-8 w-full max-w-md shrink-0 flex flex-col gap-4 pb-2 sm:mt-10 sm:gap-5 sm:pb-3">
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
