<template>
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

      <div class="hidden items-center gap-2 sm:flex">
        <UButton variant="ghost" color="neutral" size="md" @click="goToHowItWorks"> Comment ça marche </UButton>
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

      <button
        type="button"
        class="flex size-10 items-center justify-center rounded-lg transition-colors hover:bg-(--app-surface-2) sm:hidden"
        :aria-expanded="isMobileMenuOpen"
        aria-label="Menu"
        @click="isMobileMenuOpen = !isMobileMenuOpen"
      >
        <UIcon :name="isMobileMenuOpen ? 'i-lucide-x' : 'i-lucide-menu'" class="text-highlighted size-5" />
      </button>
    </div>

    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-2"
    >
      <div
        v-if="isMobileMenuOpen"
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
              @click="isMobileMenuOpen = false"
            >
              {{ isLoggedIn ? 'Dashboard' : 'Connexion' }}
            </UButton>
          </span>
          <UButton to="/request" color="primary" size="lg" block @click="isMobileMenuOpen = false">
            Demander l'accès
          </UButton>
        </div>
      </div>
    </Transition>
  </nav>
</template>

<script lang="ts" setup>
import type { Ref } from 'vue'
import type { RouteLocationNormalizedLoaded } from 'vue-router'
import logoUrl from '~/assets/images/logo-goupix-dev-256x256.png'

const route: RouteLocationNormalizedLoaded = useRoute()
const { isLoggedIn, authResolved }: ReturnType<typeof useAuth> = useAuth()

const HOW_IT_WORKS_HASH: string = '#comment-ca-marche'

const isMobileMenuOpen: Ref<boolean> = ref(false)

/**
 * Mène à « Comment ça marche » : défilement doux sur l'accueil, ouverture de l'accueil à cette section ailleurs.
 * @returns {Promise<void>} Résolue une fois le défilement ou la navigation lancés.
 */
async function goToHowItWorks(): Promise<void> {
  isMobileMenuOpen.value = false
  if (route.path === '/') {
    document.querySelector(HOW_IT_WORKS_HASH)?.scrollIntoView({ behavior: 'smooth' })
    return
  }
  await navigateTo({ path: '/', hash: HOW_IT_WORKS_HASH })
}
</script>
