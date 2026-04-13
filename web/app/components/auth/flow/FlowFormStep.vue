<script setup lang="ts">
defineProps<{
  /** 0 = vide, 1–4 progression remplissage annonce */
  formFill: number
}>()
</script>

<template>
  <div class="absolute inset-0 flex flex-col justify-center gap-2 overflow-y-auto p-1.5 sm:gap-2.5 sm:p-2">
    <p class="text-center text-[0.65rem] font-medium text-highlighted sm:text-xs">
      Fiche annonce · préremplie
    </p>
    <div class="flex gap-2 rounded-lg border border-default/60 bg-elevated/80 p-2 ring-1 ring-default/30">
      <!-- Vignette « photo » -->
      <div
        class="relative h-[5.25rem] w-14 shrink-0 overflow-hidden rounded-md bg-linear-to-br from-primary/30 to-default/40 ring-1 ring-default/40 sm:h-24 sm:w-16"
      >
        <div
          class="absolute inset-0 flex items-center justify-center transition-opacity duration-500"
          :class="formFill >= 1 ? 'opacity-100' : 'opacity-25'"
        >
          <UIcon name="i-lucide-image" class="size-6 text-default/50" />
        </div>
        <div
          v-if="formFill >= 1"
          class="absolute inset-x-0 bottom-0 h-1 bg-success/60 transition-all duration-700"
        />
      </div>
      <div class="min-w-0 flex-1 space-y-1.5">
        <div>
          <div class="mb-0.5 h-1.5 w-14 rounded bg-default/35" />
          <div
            class="h-6 overflow-hidden rounded-md bg-default/20 ring-1 ring-default/40 transition-all duration-500"
            :class="formFill >= 2 ? 'opacity-100' : 'opacity-35'"
          >
            <div
              class="flex h-full items-center px-1.5 text-[0.6rem] font-medium text-highlighted transition-[width] duration-700 ease-out"
              :style="{ width: formFill >= 2 ? '100%' : '0%', overflow: 'hidden', whiteSpace: 'nowrap' }"
            >
              <span v-if="formFill >= 2" class="truncate">Pikachu V · subset</span>
            </div>
          </div>
        </div>
        <div class="flex flex-wrap items-center gap-1.5">
          <div class="h-1.5 w-8 rounded bg-default/30" />
          <div
            class="rounded px-1.5 py-0.5 text-[0.6rem] font-semibold tabular-nums transition-all duration-500"
            :class="formFill >= 3 ? 'bg-primary/20 text-primary opacity-100' : 'opacity-30'"
          >
            <span v-if="formFill >= 3">12,90 €</span>
          </div>
          <UBadge
            v-if="formFill >= 3"
            color="neutral"
            variant="subtle"
            size="sm"
            class="px-1.5 py-0 text-[0.55rem]"
          >
            NEUF
          </UBadge>
        </div>
        <div class="space-y-0.5">
          <div
            class="h-1.5 rounded bg-default/25 transition-[width] duration-700 ease-out"
            :style="{ width: formFill >= 4 ? '100%' : formFill >= 3 ? '45%' : '0%' }"
          />
          <div
            class="h-1.5 rounded bg-default/20 transition-[width] duration-700 ease-out"
            :style="{ width: formFill >= 4 ? '78%' : '0%', transitionDelay: formFill >= 4 ? '80ms' : '0ms' }"
          />
        </div>
      </div>
    </div>
    <div class="flex items-center justify-center gap-1 text-[0.6rem] text-success sm:text-[0.65rem]">
      <UIcon name="i-lucide-sparkles" class="size-3.5 shrink-0" />
      <span>Marge & prix conseillé</span>
    </div>
  </div>
</template>
