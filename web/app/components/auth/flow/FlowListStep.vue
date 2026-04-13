<script setup lang="ts">
defineProps<{
  reduceMotion: boolean
}>()
</script>

<template>
  <div class="absolute inset-0 flex flex-col items-center justify-center gap-3 overflow-y-auto p-2 sm:gap-4">
    <div
      class="w-full max-w-[24rem] overflow-hidden rounded-xl border border-default/60 bg-elevated shadow-sm ring-1 ring-default/40 sm:max-w-[30rem]"
    >
      <div
        class="flex items-center gap-2 border-b border-default/50 bg-default/25 px-3 py-2"
      >
        <div
          class="flex size-9 shrink-0 items-center justify-center rounded-full bg-[#09B1BA]/15 ring-1 ring-[#09B1BA]/35"
        >
          <UIcon name="i-simple-icons-vinted" class="size-5 text-[#09B1BA]" />
        </div>
        <div class="min-w-0 flex-1">
          <p class="truncate text-xs font-semibold text-highlighted">
            Vinted
          </p>
          <p class="truncate text-[0.65rem] text-muted">
            Déposer l’annonce
          </p>
        </div>
        <div
          class="flex size-8 items-center justify-center rounded-full bg-primary/15"
          :class="reduceMotion ? '' : 'animate-pulse'"
        >
          <UIcon name="i-lucide-send" class="size-4 text-primary" />
        </div>
      </div>
      <div class="space-y-2 px-3 py-3">
        <div class="flex items-center gap-2 text-[0.65rem] text-muted">
          <UIcon name="i-lucide-check-circle-2" class="size-3.5 shrink-0 text-success" />
          <span>Photos & texte synchronisés</span>
        </div>
        <div class="flex items-center gap-2 text-[0.65rem] text-muted">
          <UIcon name="i-lucide-check-circle-2" class="size-3.5 shrink-0 text-success" />
          <span>Prix & frais de port appliqués</span>
        </div>
        <div
          class="mt-2 flex items-center justify-center gap-2 rounded-lg bg-success/10 py-2 ring-1 ring-success/25"
        >
          <span
            class="relative flex size-2 rounded-full bg-success"
            :class="reduceMotion ? '' : 'after:absolute after:size-full after:animate-ping after:rounded-full after:bg-success/50'"
          />
          <span class="text-xs font-medium text-success">Annonce publiée</span>
        </div>
      </div>
    </div>
  </div>
</template>
