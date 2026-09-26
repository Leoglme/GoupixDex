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

      <div class="app-tile-grid">
        <GoupixDexExtensionTile
          v-for="set in serie.sets"
          :key="set.id"
          :to="setLink(set.id)"
          :name="setLabel(set)"
          :set-code="set.id"
          :summary-label="cardCountLabel(set)"
        >
          <template #logo>
            <GoupixDexCatalogSetLogo
              :logo="set.logo"
              :symbol="set.symbol"
              :cover="set.cover"
              :set-id="set.id"
              :locale="catalogLocale"
              :name="setLabel(set)"
            />
          </template>
        </GoupixDexExtensionTile>
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
