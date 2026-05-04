<template>
  <div class="grid min-h-dvh w-full grid-cols-1 grid-rows-[auto_1fr] lg:grid-cols-2 lg:grid-rows-1">
    <!-- Zone marque -->
    <aside
      class="border-default from-primary/15 via-default to-default relative flex min-w-0 flex-col gap-8 border-b bg-linear-to-br px-6 pt-8 pb-6 sm:px-10 sm:pt-10 sm:pb-8 lg:min-h-dvh lg:justify-between lg:gap-12 lg:border-e lg:border-b-0 lg:px-14 lg:py-16 lg:pb-16 xl:px-20"
    >
      <div class="space-y-8 lg:space-y-10">
        <NuxtLink
          to="/"
          class="hover:bg-elevated/50 focus-visible:ring-primary -ms-1 inline-flex w-fit items-center gap-3 rounded-lg px-1 py-1 transition-colors focus-visible:ring-2 focus-visible:outline-none"
        >
          <span
            class="bg-elevated/60 ring-default/40 flex size-11 shrink-0 items-center justify-center overflow-hidden rounded-lg ring-1"
          >
            <img :src="logoUrl" alt="GoupixDex" class="size-9 object-contain" width="36" height="36" />
          </span>
          <span class="text-highlighted text-lg font-semibold tracking-tight"> GoupixDex </span>
        </NuxtLink>
        <div class="space-y-4">
          <h1 class="text-highlighted text-3xl leading-tight font-semibold tracking-tight sm:text-4xl">
            Rejoignez les premiers utilisateurs
          </h1>
          <p class="text-muted max-w-md text-base leading-relaxed text-pretty">
            GoupixDex est en accès limité. Laissez vos coordonnées et soyez parmi les premiers à automatiser vos ventes
            de cartes Pokémon TCG sur Vinted.
          </p>
        </div>
      </div>

      <!-- Animation visible uniquement en desktop -->
      <div
        class="hidden min-h-0 w-full min-w-0 shrink-0 lg:flex lg:flex-1 lg:flex-col lg:items-center lg:justify-center lg:py-2"
      >
        <div class="w-full max-w-[14rem]">
          <GoupixDexSellingCardAnimation />
        </div>
      </div>

      <div class="hidden shrink-0 lg:block">
        <div class="text-muted flex items-center gap-2 text-sm">
          <UIcon name="i-lucide-users" class="text-primary size-4 shrink-0" />
          <span>Places limitées · Réponse sous 24h</span>
        </div>
      </div>
    </aside>

    <!-- Zone formulaire -->
    <main
      class="bg-elevated flex min-h-0 flex-col px-6 pt-6 pb-4 sm:px-10 sm:pt-8 sm:pb-5 lg:min-h-dvh lg:px-14 lg:py-16 xl:px-20"
    >
      <div class="flex min-h-0 flex-1 flex-col justify-start pt-3 lg:justify-center lg:pt-0">
        <div class="mx-auto w-full max-w-md">
          <!-- Success state -->
          <div v-if="submitted">
            <div class="mb-10 space-y-5 text-center">
              <div
                class="bg-success/15 text-success ring-success/30 mx-auto flex size-16 items-center justify-center rounded-full ring-2"
              >
                <UIcon name="i-lucide-check" class="size-8" />
              </div>
              <h2 class="text-highlighted text-2xl font-semibold sm:text-3xl">Demande envoyée !</h2>
              <p class="text-muted mx-auto max-w-sm text-base leading-relaxed">
                Merci pour votre intérêt. Nous vous recontacterons à
                <strong class="text-highlighted">{{ email }}</strong>
                dès qu'une place se libère.
              </p>
            </div>
            <div class="flex flex-col gap-3">
              <UButton to="/" variant="outline" color="neutral" size="lg" block>
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
                  class="text-muted hover:bg-default hover:text-highlighted flex size-8 items-center justify-center rounded-lg transition-colors"
                >
                  <UIcon name="i-lucide-arrow-left" class="size-4" />
                </NuxtLink>
              </div>
              <h2 class="text-highlighted text-2xl font-semibold">Demander l'accès</h2>
              <p class="text-muted text-sm">
                Remplissez le formulaire ci-dessous, nous reviendrons vers vous rapidement.
              </p>
            </div>

            <UAlert
              v-if="errorMsg"
              color="error"
              variant="subtle"
              icon="i-lucide-circle-alert"
              :title="errorMsg"
              class="mb-5"
            />

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

            <p class="text-muted mt-6 text-center text-xs">
              Votre email ne sera utilisé que pour vous contacter au sujet de GoupixDex.
            </p>
          </template>
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
import type { Ref } from 'vue'
import logoUrl from '~/assets/images/logo-goupix-dev-256x256.png'

definePageMeta({
  layout: 'auth',
})

useGoupixPageSeo(
  'Demander un accès',
  "Rejoignez la liste d'attente GoupixDex pour automatiser vos ventes de cartes Pokémon TCG sur Vinted dès l'ouverture.",
)

const { submitAccessRequest } = useAccessRequests()

const email: Ref<string> = ref('')
const message: Ref<string> = ref('')
const submitted: Ref<boolean> = ref(false)
const loading: Ref<boolean> = ref(false)
const errorMsg: Ref<string | null> = ref(null)

async function handleSubmit(): Promise<void> {
  if (!email.value) {
    return
  }
  errorMsg.value = null
  loading.value = true
  try {
    await submitAccessRequest({
      email: email.value.trim(),
      message: message.value.trim() || null,
    })
    submitted.value = true
  } catch (e) {
    errorMsg.value = apiErrorMessage(e)
  } finally {
    loading.value = false
  }
}
</script>
