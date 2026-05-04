<template>
  <div class="absolute inset-0 flex flex-col justify-center gap-2 overflow-y-auto p-1.5 sm:gap-2.5 sm:p-2">
    <p class="text-highlighted text-center text-[0.65rem] font-medium sm:text-xs">Fiche annonce · préremplie</p>
    <div class="border-default/60 bg-elevated/80 ring-default/30 flex gap-2 rounded-lg border p-2 ring-1">
      <!-- Vignette « photo » -->
      <div
        class="from-primary/30 to-default/40 ring-default/40 relative h-[5.25rem] w-14 shrink-0 overflow-hidden rounded-md bg-linear-to-br ring-1 sm:h-24 sm:w-16"
      >
        <div
          class="absolute inset-0 flex items-center justify-center transition-opacity duration-500"
          :class="formFill >= 1 ? 'opacity-100' : 'opacity-25'"
        >
          <UIcon name="i-lucide-image" class="text-default/50 size-6" />
        </div>
        <div v-if="formFill >= 1" class="bg-success/60 absolute inset-x-0 bottom-0 h-1 transition-all duration-700" />
      </div>
      <div class="min-w-0 flex-1 space-y-1.5">
        <div>
          <div class="bg-default/35 mb-0.5 h-1.5 w-14 rounded" />
          <div
            class="bg-default/20 ring-default/40 h-6 overflow-hidden rounded-md ring-1 transition-all duration-500"
            :class="formFill >= 2 ? 'opacity-100' : 'opacity-35'"
          >
            <div
              class="text-highlighted flex h-full items-center px-1.5 text-[0.6rem] font-medium transition-[width] duration-700 ease-out"
              :style="{ width: formFill >= 2 ? '100%' : '0%', overflow: 'hidden', whiteSpace: 'nowrap' }"
            >
              <span v-if="formFill >= 2" class="truncate">Pikachu V · subset</span>
            </div>
          </div>
        </div>
        <div class="flex flex-wrap items-center gap-1.5">
          <div class="bg-default/30 h-1.5 w-8 rounded" />
          <div
            class="rounded px-1.5 py-0.5 text-[0.6rem] font-semibold tabular-nums transition-all duration-500"
            :class="formFill >= 3 ? 'bg-primary/20 text-primary opacity-100' : 'opacity-30'"
          >
            <span v-if="formFill >= 3">12,90 €</span>
          </div>
          <UBadge v-if="formFill >= 3" color="neutral" variant="subtle" size="sm" class="px-1.5 py-0 text-[0.55rem]">
            NEUF
          </UBadge>
        </div>
        <div class="space-y-0.5">
          <div
            class="bg-default/25 h-1.5 rounded transition-[width] duration-700 ease-out"
            :style="{ width: formFill >= 4 ? '100%' : formFill >= 3 ? '45%' : '0%' }"
          />
          <div
            class="bg-default/20 h-1.5 rounded transition-[width] duration-700 ease-out"
            :style="{ width: formFill >= 4 ? '78%' : '0%', transitionDelay: formFill >= 4 ? '80ms' : '0ms' }"
          />
        </div>
      </div>
    </div>
    <div class="text-success flex items-center justify-center gap-1 text-[0.6rem] sm:text-[0.65rem]">
      <UIcon name="i-lucide-sparkles" class="size-3.5 shrink-0" />
      <span>Marge & prix conseillé</span>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  /** 0 = empty, 1–4 listing form fill progress */
  formFill: number
}>()
</script>
