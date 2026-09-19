<template>
  <div class="space-y-8">
    <p v-if="extensionFilter.trim() && !filteredSeries.length" class="text-muted text-sm">
      Aucune extension ne correspond à « {{ extensionFilter.trim() }} ».
    </p>

    <section v-for="serie in filteredSeries" :key="serie.id" class="space-y-4">
      <div class="flex flex-wrap items-baseline gap-3">
        <h2 class="text-highlighted text-xl font-semibold tracking-tight">
          {{ seriesLabel(serie) }}
        </h2>
        <span class="text-muted text-sm tabular-nums"
          >{{ serie.sets.length }} set{{ serie.sets.length > 1 ? 's' : '' }}</span
        >
      </div>

      <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
        <NuxtLink
          v-for="set in serie.sets"
          :key="set.id"
          :to="setLink(set.id)"
          class="border-default bg-elevated/40 group hover:border-primary/40 flex flex-col gap-3 rounded-xl border p-4 transition hover:shadow-md"
        >
          <div class="flex h-14 items-center justify-center">
            <GoupixDexCatalogSetLogo :logo="set.logo" :symbol="set.symbol" :cover="set.cover" :name="setLabel(set)" />
          </div>
          <div class="mt-auto min-w-0">
            <p class="text-highlighted group-hover:text-primary truncate text-sm leading-tight font-medium">
              {{ setLabel(set) }}
            </p>
            <p class="text-muted mt-1 flex flex-wrap items-center gap-2 text-xs">
              <span class="bg-muted/30 num rounded px-1.5 py-0.5 font-mono uppercase">{{ set.id }}</span>
              <span v-if="cardCountLabel(set)" class="tabular-nums">{{ cardCountLabel(set) }}</span>
            </p>
          </div>
        </NuxtLink>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import type { CatalogLocale, TcgdexSeriesWithSets, TcgdexSetBrief } from '~/composables/useCardCatalog'

const props = defineProps<{
  series: TcgdexSeriesWithSets[]
  catalogLocale: CatalogLocale
  extensionFilter: string
}>()

const filteredSeries = computed(() => {
  const needle = props.extensionFilter.trim().toLowerCase()
  if (!needle) {
    return props.series
  }
  return props.series
    .map((serie) => {
      const serieMatch = seriesLabel(serie).toLowerCase().includes(needle) || serie.id.toLowerCase().includes(needle)
      const sets = serieMatch
        ? serie.sets
        : serie.sets.filter((s) => setLabel(s).toLowerCase().includes(needle) || s.id.toLowerCase().includes(needle))
      return { ...serie, sets }
    })
    .filter((serie) => serie.sets.length > 0)
})

function seriesLabel(serie: TcgdexSeriesWithSets): string {
  return serie.display_name?.trim() || serie.name?.trim() || serie.id
}

function setLabel(set: TcgdexSetBrief): string {
  return set.display_name?.trim() || set.name?.trim() || set.id
}

function cardCountLabel(set: TcgdexSetBrief): string | null {
  const n = set.cardCount?.total ?? set.cardCount?.official
  return n ? `${n} cartes` : null
}

function setLink(setId: string): string {
  const loc = props.catalogLocale
  const q = loc === 'fr' ? '' : `?locale=${encodeURIComponent(loc)}`
  return `/collection/add/${encodeURIComponent(setId)}${q}`
}
</script>
