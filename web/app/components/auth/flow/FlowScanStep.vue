<script setup lang="ts">
defineProps<{
  reduceMotion: boolean
}>()
</script>

<template>
  <div class="absolute inset-0 flex flex-col items-center justify-center gap-3 p-2 sm:gap-4 sm:p-3">
    <div
      class="relative aspect-[5/7] w-[5.75rem] rounded-lg bg-linear-to-br from-primary/20 to-elevated ring-2 ring-default/50 sm:w-24"
    >
      <div
        v-if="!reduceMotion"
        class="flow-scan-line pointer-events-none absolute inset-x-1.5 top-0 h-0.5 rounded-full bg-primary shadow-[0_0_10px_rgba(232,97,18,0.55)]"
      />
      <UIcon
        name="i-lucide-scan-line"
        class="absolute bottom-1 right-1 size-5 text-primary sm:size-6"
      />
    </div>
    <span class="max-w-[16rem] text-center text-sm font-medium text-highlighted sm:text-base">Lecture & reconnaissance</span>
  </div>
</template>

<style scoped>
@keyframes flow-scan {
  0% {
    top: 0.25rem;
    opacity: 0.85;
  }
  50% {
    top: calc(100% - 0.35rem);
    opacity: 1;
  }
  100% {
    top: 0.25rem;
    opacity: 0.85;
  }
}

.flow-scan-line {
  animation: flow-scan 1.6s ease-in-out infinite;
}

@media (prefers-reduced-motion: reduce) {
  .flow-scan-line {
    animation: none;
    top: 50%;
  }
}
</style>
