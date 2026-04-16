<script setup lang="ts">
/**
 * Même esprit que l'overlay « vendu » de SellingCardAnimation : carte générique + check + badge.
 */
defineProps<{
  reduceMotion: boolean
}>()
</script>

<template>
  <div class="absolute inset-0 flex flex-col items-center justify-center gap-4 p-3 sm:gap-5">
    <div
      class="flow-sale-card relative flex aspect-[5/7] w-[8rem] flex-col overflow-hidden rounded-xl bg-elevated shadow-lg ring-2 ring-success/55 sm:w-[9rem]"
      :class="reduceMotion ? '' : 'flow-sale-card--motion'"
    >
      <div
        class="relative m-2 flex min-h-0 flex-1 flex-col rounded-lg bg-linear-to-br from-primary/25 via-elevated to-secondary-400/20"
      >
        <div class="m-2 h-2 w-8 rounded-full bg-default/40" />
        <div class="mx-2 flex min-h-0 flex-1 flex-col justify-center gap-1 px-2 pb-2">
          <div class="h-1 w-full rounded bg-default/30" />
          <div class="h-1 w-[75%] rounded bg-default/25" />
          <div class="h-1 w-[55%] rounded bg-default/20" />
        </div>
      </div>
      <div class="flex shrink-0 items-center justify-between gap-2 border-t border-default/60 bg-default/40 px-2.5 py-2">
        <div class="h-2 w-12 rounded bg-default/35" />
        <div class="h-2 w-6 rounded bg-primary/45" />
      </div>
      <div
        class="flow-sale-overlay absolute inset-0 flex flex-col items-center justify-center gap-2 rounded-xl bg-default/50 backdrop-blur-[3px]"
        :class="reduceMotion ? '' : 'flow-sale-overlay--motion'"
      >
        <span
          class="flow-sale-check flex size-11 items-center justify-center rounded-full bg-success/20 text-success ring-2 ring-success/50"
          :class="reduceMotion ? '' : 'flow-sale-check--motion'"
        >
          <UIcon name="i-lucide-check" class="size-6" />
        </span>
        <span
          class="inline-flex"
          :class="reduceMotion ? '' : 'flow-sale-badge--motion'"
        >
          <UBadge
            color="success"
            variant="subtle"
            size="sm"
            class="font-semibold"
          >
            Vendu
          </UBadge>
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes flow-sale-card {
  0%,
  100% {
    transform: translateY(0) rotate(-0.75deg);
  }
  50% {
    transform: translateY(-6px) rotate(0.75deg);
  }
}

@keyframes flow-sale-overlay-in {
  0% {
    opacity: 0;
  }
  100% {
    opacity: 1;
  }
}

@keyframes flow-sale-check {
  0%,
  100% {
    transform: scale(1);
    box-shadow: 0 0 0 0 rgb(34 197 94 / 0.35);
  }
  50% {
    transform: scale(1.06);
    box-shadow: 0 0 0 10px rgb(34 197 94 / 0);
  }
}

@keyframes flow-sale-badge {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-2px);
  }
}

.flow-sale-card--motion {
  animation: flow-sale-card 2.4s ease-in-out infinite;
}

.flow-sale-overlay--motion {
  animation: flow-sale-overlay-in 0.55s ease-out both;
}

.flow-sale-check--motion {
  animation: flow-sale-check 1.8s ease-in-out infinite;
  animation-delay: 0.35s;
}

.flow-sale-badge--motion {
  animation: flow-sale-badge 2s ease-in-out infinite;
  animation-delay: 0.2s;
}

@media (prefers-reduced-motion: reduce) {
  .flow-sale-card--motion,
  .flow-sale-overlay--motion,
  .flow-sale-check--motion,
  .flow-sale-badge--motion {
    animation: none;
  }

  .flow-sale-overlay--motion {
    opacity: 1;
  }
}
</style>
