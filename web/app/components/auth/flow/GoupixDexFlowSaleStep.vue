<template>
  <div class="absolute inset-0 flex flex-col items-center justify-center gap-4 p-3 sm:gap-5">
    <div
      class="flow-sale-card bg-elevated ring-success/55 relative flex aspect-[5/7] w-[8rem] flex-col overflow-hidden rounded-xl shadow-lg ring-2 sm:w-[9rem]"
      :class="reduceMotion ? '' : 'goupix-flow-sale-card--motion'"
    >
      <div
        class="from-primary/25 via-elevated to-secondary-400/20 relative m-2 flex min-h-0 flex-1 flex-col rounded-lg bg-linear-to-br"
      >
        <div class="bg-default/40 m-2 h-2 w-8 rounded-full" />
        <div class="mx-2 flex min-h-0 flex-1 flex-col justify-center gap-1 px-2 pb-2">
          <div class="bg-default/30 h-1 w-full rounded" />
          <div class="bg-default/25 h-1 w-[75%] rounded" />
          <div class="bg-default/20 h-1 w-[55%] rounded" />
        </div>
      </div>
      <div
        class="border-default/60 bg-default/40 flex shrink-0 items-center justify-between gap-2 border-t px-2.5 py-2"
      >
        <div class="bg-default/35 h-2 w-12 rounded" />
        <div class="bg-primary/45 h-2 w-6 rounded" />
      </div>
      <div
        class="flow-sale-overlay bg-default/50 absolute inset-0 flex flex-col items-center justify-center gap-2 rounded-xl backdrop-blur-[3px]"
        :class="reduceMotion ? '' : 'goupix-flow-sale-overlay--motion'"
      >
        <span
          class="flow-sale-check bg-success/20 text-success ring-success/50 flex size-11 items-center justify-center rounded-full ring-2"
          :class="reduceMotion ? '' : 'goupix-flow-sale-check--motion'"
        >
          <UIcon name="i-lucide-check" class="size-6" />
        </span>
        <span class="inline-flex" :class="reduceMotion ? '' : 'goupix-flow-sale-badge--motion'">
          <UBadge color="success" variant="subtle" size="sm" class="font-semibold"> Vendu </UBadge>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * Same idea as SellingCardAnimation’s “sold” overlay: generic card + check + badge.
 */
defineProps<{
  reduceMotion: boolean
}>()
</script>
