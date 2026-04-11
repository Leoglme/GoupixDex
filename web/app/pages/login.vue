<script setup lang="ts">
import logoUrl from '~/assets/images/logo-goupix-dev-256x256.png'

definePageMeta({
  layout: 'auth',
  middleware: 'guest'
})
</script>

<template>
  <UCard class="w-full max-w-md shadow-lg">
    <template #header>
      <div class="flex flex-col items-center gap-3 py-2">
        <img
          :src="logoUrl"
          alt="GoupixDex"
          class="size-16 rounded-xl object-cover ring ring-default"
        >
        <div class="text-center">
          <h1 class="text-lg font-semibold text-highlighted">
            GoupixDex
          </h1>
          <p class="text-sm text-muted">
            Connexion à votre espace
          </p>
        </div>
      </div>
    </template>
    <LoginForm />
  </UCard>
</template>
