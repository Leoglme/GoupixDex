<template>
  <article
    class="group border-default bg-elevated/30 hover:border-primary/40 hover:bg-elevated/60 flex items-center gap-3 rounded-xl border p-3 transition-colors sm:gap-4 sm:p-4"
  >
    <div class="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary text-base font-semibold tabular-nums sm:size-12 sm:text-lg">
      {{ row.rank }}
    </div>

    <div class="bg-muted/30 relative size-16 shrink-0 overflow-hidden rounded-lg sm:size-20">
      <img
        v-if="imgSrc"
        :src="imgSrc"
        :srcset="imgSrcset"
        :alt="row.display_title"
        loading="lazy"
        decoding="async"
        class="size-full object-cover transition-transform duration-300 group-hover:scale-[1.04]"
      />
      <div v-else class="text-muted flex size-full items-center justify-center">
        <UIcon name="i-lucide-image-off" class="size-6" />
      </div>
    </div>

    <div class="min-w-0 flex-1">
      <h3 class="text-highlighted line-clamp-2 text-sm leading-snug font-medium sm:text-base">
        {{ row.display_title }}
      </h3>
      <div class="text-muted mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
        <span v-if="row.grade" class="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 font-medium text-amber-600 dark:text-amber-400">
          <UIcon name="i-lucide-shield-check" class="size-3" />
          {{ row.grade }}
        </span>
        <span v-if="medianFormatted" class="inline-flex items-center gap-1">
          <UIcon name="i-lucide-trending-up" class="size-3" />
          médiane {{ medianFormatted }}
        </span>
        <span v-if="row.approx_hours_min !== null" class="inline-flex items-center gap-1">
          <UIcon name="i-lucide-clock" class="size-3" />
          dernière vente {{ approxRecentLabel }}
        </span>
      </div>
    </div>

    <div class="flex shrink-0 flex-col items-end gap-1 text-right">
      <span class="text-primary text-base font-semibold tabular-nums sm:text-lg">
        {{ row.count }} {{ row.count > 1 ? 'ventes' : 'vente' }}
      </span>
      <span v-if="totalFormatted" class="text-muted text-xs tabular-nums">
        {{ totalFormatted }} cumulés
      </span>
      <UButton
        v-if="row.sample_listing_url"
        :to="row.sample_listing_url"
        target="_blank"
        rel="noopener"
        size="xs"
        color="neutral"
        variant="subtle"
        icon="i-lucide-external-link"
        class="mt-1"
      >
        Voir un exemplaire
      </UButton>
    </div>
  </article>
</template>

<script setup lang="ts">
import type { EbaySoldTopRow } from '~/composables/useEbaySoldTop'

const props = defineProps<{
  row: EbaySoldTopRow
}>()

const eur = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2
})

const medianFormatted = computed(() => {
  const v = props.row.median_price_eur
  return v == null || !Number.isFinite(v) ? '' : eur.format(v)
})

const totalFormatted = computed(() => {
  const v = props.row.total_value_eur
  return v == null || !Number.isFinite(v) || v <= 0 ? '' : eur.format(v)
})

const approxRecentLabel = computed(() => formatRelativeHours(props.row.approx_hours_min))

/** Vignettes ~80 px sur grand écran : 225 nominal, 500 pour la 2x retina. */
const imgSrc = computed(() => upgradeEbayImage(props.row.image_url, 225))
const imgSrcset = computed(() => ebayImageSrcset(props.row.image_url, 225))
</script>
