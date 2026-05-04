<template>
  <div class="absolute inset-0 flex flex-col items-center justify-center gap-3 overflow-y-auto p-2 sm:gap-4">
    <div
      class="border-default/60 bg-elevated ring-default/40 w-full max-w-[24rem] overflow-hidden rounded-xl border shadow-sm ring-1 sm:max-w-[30rem]"
    >
      <div class="border-default/50 bg-default/25 flex items-center gap-2 border-b px-3 py-2">
        <div
          class="flex size-9 shrink-0 items-center justify-center rounded-full bg-[#09B1BA]/15 ring-1 ring-[#09B1BA]/35"
        >
          <UIcon name="i-simple-icons-vinted" class="size-5 text-[#09B1BA]" />
        </div>
        <div class="min-w-0 flex-1">
          <p class="text-highlighted truncate text-xs font-semibold">Vinted</p>
          <p class="text-muted truncate text-[0.65rem]">Déposer l'annonce</p>
        </div>
        <div
          class="bg-primary/15 flex size-8 items-center justify-center rounded-full"
          :class="reduceMotion ? '' : 'animate-pulse'"
        >
          <UIcon name="i-lucide-send" class="text-primary size-4" />
        </div>
      </div>
      <div class="space-y-2 px-3 py-3">
        <div class="text-muted flex items-center gap-2 text-[0.65rem]">
          <UIcon name="i-lucide-check-circle-2" class="text-success size-3.5 shrink-0" />
          <span>Photos & texte synchronisés</span>
        </div>
        <div class="text-muted flex items-center gap-2 text-[0.65rem]">
          <UIcon name="i-lucide-check-circle-2" class="text-success size-3.5 shrink-0" />
          <span>Prix & frais de port appliqués</span>
        </div>
        <div class="bg-success/10 ring-success/25 mt-2 flex items-center justify-center gap-2 rounded-lg py-2 ring-1">
          <span
            class="bg-success relative flex size-2 rounded-full"
            :class="
              reduceMotion
                ? ''
                : 'after:bg-success/50 after:absolute after:size-full after:animate-ping after:rounded-full'
            "
          />
          <span class="text-success text-xs font-medium">Annonce publiée</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  reduceMotion: boolean
}>()
</script>
