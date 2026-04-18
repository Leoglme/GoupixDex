<script setup lang="ts">
import goupixLogoUrl from '~/assets/images/logo-goupixdex.svg'

defineProps<{
  reduceMotion: boolean
}>()
</script>

<template>
  <div class="absolute inset-0 flex flex-col items-center justify-center gap-4 p-3 sm:gap-5 sm:p-4">
    <div class="relative flex w-full max-w-[22rem] items-center justify-between gap-2 sm:max-w-[26rem]">
      <!-- GoupixDex -->
      <div
        class="relative z-10 flex w-[5.25rem] flex-col items-center gap-2 rounded-xl border border-primary/35 bg-linear-to-br from-primary/15 to-elevated px-2 py-3 shadow-sm ring-1 ring-default/40 sm:w-[6rem] sm:py-4"
      >
        <div
          class="flex size-11 items-center justify-center overflow-hidden rounded-lg bg-primary/10 ring-1 ring-primary/25 sm:size-12"
        >
          <img
            :src="goupixLogoUrl"
            alt=""
            width="48"
            height="48"
            class="size-10 object-contain sm:size-11"
            loading="lazy"
            decoding="async"
          />
        </div>
        <span class="text-center text-[0.65rem] font-semibold leading-tight text-highlighted sm:text-xs">
          GoupixDex
        </span>
      </div>

      <!-- Connector -->
      <div class="relative min-w-0 flex-1 px-1">
        <div
          class="relative h-1 overflow-hidden rounded-full bg-default/80 ring-1 ring-default/50"
          aria-hidden="true"
        >
          <div
            class="flow-sync-pulse absolute inset-y-0 w-1/3 rounded-full bg-linear-to-r from-primary/20 via-primary to-primary/60"
            :class="reduceMotion ? 'opacity-80' : ''"
          />
        </div>
        <div
          class="mt-1.5 flex justify-center gap-1 text-[0.6rem] font-medium text-muted sm:text-[0.65rem]"
        >
          <UIcon name="i-lucide-arrow-left-right" class="size-3 text-primary/80" />
          <span>Données synchronisées</span>
        </div>
      </div>

      <!-- Vinted -->
      <div
        class="relative z-10 flex w-[5.25rem] flex-col items-center gap-2 rounded-xl border border-[#09B1BA]/35 bg-elevated px-2 py-3 shadow-sm ring-1 ring-default/40 sm:w-[6rem] sm:py-4"
      >
        <div
          class="flex size-11 items-center justify-center rounded-full bg-[#09B1BA]/15 ring-1 ring-[#09B1BA]/40 sm:size-12"
        >
          <UIcon name="i-simple-icons-vinted" class="size-6 text-[#09B1BA] sm:size-7" />
        </div>
        <span class="text-center text-[0.65rem] font-semibold leading-tight text-highlighted sm:text-xs">
          Vinted
        </span>
      </div>
    </div>

    <p class="max-w-[18rem] text-center text-sm font-medium text-muted sm:max-w-none sm:text-base">
      Collection, annonces en ligne et ventes importées dans votre espace
    </p>
  </div>
</template>

<style scoped>
@keyframes flow-sync-pulse {
  0% {
    left: -35%;
    opacity: 0.85;
  }
  50% {
    left: 100%;
    opacity: 1;
  }
  100% {
    left: -35%;
    opacity: 0.85;
  }
}

.flow-sync-pulse {
  animation: flow-sync-pulse 2.4s ease-in-out infinite;
}

@media (prefers-reduced-motion: reduce) {
  .flow-sync-pulse {
    animation: none;
    left: 32%;
    opacity: 1;
  }
}
</style>
