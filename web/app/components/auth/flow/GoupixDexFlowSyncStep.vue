<template>
  <div class="absolute inset-0 flex flex-col items-center justify-center gap-4 p-3 sm:gap-5 sm:p-4">
    <div class="relative flex w-full max-w-[22rem] items-center justify-between gap-2 sm:max-w-[26rem]">
      <!-- GoupixDex -->
      <div
        class="border-primary/35 from-primary/15 to-elevated ring-default/40 relative z-10 flex w-[5.25rem] flex-col items-center gap-2 rounded-xl border bg-linear-to-br px-2 py-3 shadow-sm ring-1 sm:w-[6rem] sm:py-4"
      >
        <div
          class="bg-primary/10 ring-primary/25 flex size-11 items-center justify-center overflow-hidden rounded-lg ring-1 sm:size-12"
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
        <span class="text-highlighted text-center text-[0.65rem] leading-tight font-semibold sm:text-xs">
          GoupixDex
        </span>
      </div>

      <!-- Connector -->
      <div class="relative min-w-0 flex-1 px-1">
        <div class="bg-default/80 ring-default/50 relative h-1 overflow-hidden rounded-full ring-1" aria-hidden="true">
          <div
            class="goupix-flow-sync-pulse from-primary/20 via-primary to-primary/60 absolute inset-y-0 w-1/3 rounded-full bg-linear-to-r"
            :class="reduceMotion ? 'opacity-80' : ''"
          />
        </div>
        <div class="text-muted mt-1.5 flex justify-center gap-1 text-[0.6rem] font-medium sm:text-[0.65rem]">
          <UIcon name="i-lucide-arrow-left-right" class="text-primary/80 size-3" />
          <span>Données synchronisées</span>
        </div>
      </div>

      <!-- Vinted -->
      <div
        class="bg-elevated ring-default/40 relative z-10 flex w-[5.25rem] flex-col items-center gap-2 rounded-xl border border-[#09B1BA]/35 px-2 py-3 shadow-sm ring-1 sm:w-[6rem] sm:py-4"
      >
        <div
          class="flex size-11 items-center justify-center rounded-full bg-[#09B1BA]/15 ring-1 ring-[#09B1BA]/40 sm:size-12"
        >
          <UIcon name="i-simple-icons-vinted" class="size-6 text-[#09B1BA] sm:size-7" />
        </div>
        <span class="text-highlighted text-center text-[0.65rem] leading-tight font-semibold sm:text-xs"> Vinted </span>
      </div>
    </div>

    <p class="text-muted max-w-[18rem] text-center text-sm font-medium sm:max-w-none sm:text-base">
      Collection, annonces en ligne et ventes importées dans votre espace
    </p>
  </div>
</template>

<script setup lang="ts">
import goupixLogoUrl from '~/assets/images/logo-goupixdex.svg'

defineProps<{
  reduceMotion: boolean
}>()
</script>
