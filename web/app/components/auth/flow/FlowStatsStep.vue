<script setup lang="ts">
defineProps<{
  reduceMotion: boolean
}>()
</script>

<template>
  <div class="absolute inset-0 flex flex-col items-center justify-center gap-2 p-2 sm:gap-2.5 sm:p-3">
    <p class="shrink-0 text-center text-sm font-medium text-highlighted sm:text-base">
      Tableau de bord
    </p>
    <div
      class="flex h-[10rem] w-full max-w-[18rem] items-end justify-center gap-3 sm:h-[13rem] sm:max-w-xs sm:gap-4 lg:h-[15rem]"
    >
      <div
        class="w-9 rounded-t-md bg-primary/40 transition-all duration-700 sm:w-11 lg:w-[3.25rem]"
        :class="reduceMotion ? 'h-[40%]' : 'h-[40%] flow-bar-pulse'"
        style="animation-delay: 0ms"
      />
      <div
        class="w-9 rounded-t-md bg-primary/60 transition-all duration-700 sm:w-11 lg:w-[3.25rem]"
        :class="reduceMotion ? 'h-[65%]' : 'h-[65%] flow-bar-pulse'"
        style="animation-delay: 120ms"
      />
      <div
        class="w-9 rounded-t-md bg-secondary-400/50 transition-all duration-700 sm:w-11 lg:w-[3.25rem]"
        :class="reduceMotion ? 'h-[50%]' : 'h-[50%] flow-bar-pulse'"
        style="animation-delay: 240ms"
      />
      <div
        class="w-9 rounded-t-md bg-primary/50 transition-all duration-700 sm:w-11 lg:w-[3.25rem]"
        :class="reduceMotion ? 'h-[85%]' : 'h-[85%] flow-bar-pulse'"
        style="animation-delay: 360ms"
      />
    </div>
    <div class="shrink-0 flex justify-center gap-6 text-xs font-medium text-muted sm:gap-8 sm:text-sm">
      <span>CA</span>
      <span>Marge</span>
      <span>Stock</span>
    </div>
  </div>
</template>

<style scoped>
@keyframes flow-bar {
  0%,
  100% {
    opacity: 0.75;
    transform: scaleY(1);
  }
  50% {
    opacity: 1;
    transform: scaleY(1.06);
  }
}

.flow-bar-pulse {
  transform-origin: bottom;
  animation: flow-bar 1.2s ease-in-out infinite;
}

@media (prefers-reduced-motion: reduce) {
  .flow-bar-pulse {
    animation: none;
  }
}
</style>
