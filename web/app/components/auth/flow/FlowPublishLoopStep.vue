<script setup lang="ts">
const props = defineProps<{
  reduceMotion: boolean
}>()

const phase = ref<'vinted' | 'ebay'>('vinted')
let timer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  if (props.reduceMotion) return
  timer = setInterval(() => {
    phase.value = phase.value === 'vinted' ? 'ebay' : 'vinted'
  }, 3200)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div class="absolute inset-0 flex flex-col items-center justify-center gap-3 overflow-y-auto p-2 sm:gap-4">
    <div class="relative min-h-[12.5rem] w-full max-w-[24rem] sm:max-w-[30rem]">
      <!-- Vinted -->
      <div
        class="absolute inset-0 transition-all duration-500 ease-out"
        :class="reduceMotion || phase === 'vinted'
          ? 'z-10 translate-y-0 opacity-100'
          : 'z-0 translate-y-2 opacity-0 pointer-events-none'"
      >
        <div
          class="w-full overflow-hidden rounded-xl border border-default/60 bg-elevated shadow-sm ring-1 ring-default/40"
        >
          <div class="flex items-center gap-2 border-b border-default/50 bg-default/25 px-3 py-2">
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
                Déposer l'annonce
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

      <!-- eBay -->
      <div
        v-if="!reduceMotion"
        class="absolute inset-0 transition-all duration-500 ease-out"
        :class="phase === 'ebay'
          ? 'z-10 translate-y-0 opacity-100'
          : 'z-0 translate-y-2 opacity-0 pointer-events-none'"
      >
        <div
          class="w-full overflow-hidden rounded-xl border border-default/60 bg-elevated shadow-sm ring-1 ring-default/40"
        >
          <div class="flex items-center gap-2 border-b border-default/50 bg-default/25 px-3 py-2">
            <div
              class="flex size-9 shrink-0 items-center justify-center rounded-full bg-default/50 ring-1 ring-default/35"
            >
              <EbayLogoGradient class="h-6 w-6 sm:h-7 sm:w-7" />
            </div>
            <div class="min-w-0 flex-1">
              <p class="truncate text-xs font-semibold text-highlighted">
                eBay
              </p>
              <p class="truncate text-[0.65rem] text-muted">
                Déposer l'annonce
              </p>
            </div>
            <div
              class="flex size-8 items-center justify-center rounded-full bg-[#296ef1]/12"
              :class="reduceMotion ? '' : 'animate-pulse'"
            >
              <UIcon name="i-lucide-send" class="size-4 text-[#296ef1]" />
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
    </div>

    <p
      v-if="!reduceMotion"
      class="text-center text-xs font-medium text-muted"
    >
      {{ phase === 'vinted' ? 'Publication Vinted' : 'Publication eBay' }}
      <span class="mx-1 text-muted/50">·</span>
      alternance automatique
    </p>
  </div>
</template>
