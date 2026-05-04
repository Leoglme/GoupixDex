<template>
  <div class="absolute inset-0 flex flex-col items-center justify-center gap-2 p-2 sm:gap-2.5 sm:p-3">
    <p class="text-highlighted shrink-0 text-center text-sm font-medium sm:text-base">Tableau de bord</p>
    <div
      class="flex h-[10rem] w-full max-w-[18rem] items-end justify-center gap-3 sm:h-[13rem] sm:max-w-xs sm:gap-4 lg:h-[15rem]"
    >
      <div
        class="bg-primary/40 w-9 rounded-t-md transition-all duration-700 sm:w-11 lg:w-[3.25rem]"
        :class="reduceMotion ? 'h-[40%]' : 'goupix-flow-bar-pulse h-[40%]'"
        style="animation-delay: 0ms"
      />
      <div
        class="bg-primary/60 w-9 rounded-t-md transition-all duration-700 sm:w-11 lg:w-[3.25rem]"
        :class="reduceMotion ? 'h-[65%]' : 'goupix-flow-bar-pulse h-[65%]'"
        style="animation-delay: 120ms"
      />
      <div
        class="bg-secondary-400/50 w-9 rounded-t-md transition-all duration-700 sm:w-11 lg:w-[3.25rem]"
        :class="reduceMotion ? 'h-[50%]' : 'goupix-flow-bar-pulse h-[50%]'"
        style="animation-delay: 240ms"
      />
      <div
        class="bg-primary/50 w-9 rounded-t-md transition-all duration-700 sm:w-11 lg:w-[3.25rem]"
        :class="reduceMotion ? 'h-[85%]' : 'goupix-flow-bar-pulse h-[85%]'"
        style="animation-delay: 360ms"
      />
    </div>
    <div class="text-muted flex shrink-0 justify-center gap-6 text-xs font-medium sm:gap-8 sm:text-sm">
      <span>CA</span>
      <span>Marge</span>
      <span>Stock</span>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  reduceMotion: boolean
}>()
</script>
