<template>
  <div class="flex flex-col gap-6">
    <!-- Worker fetch settings: two balanced columns (avoids a narrow “pages” column). -->
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2 md:items-start md:gap-6">
      <UFormField
        class="min-w-0"
        label="Recherche (optionnelle)"
        description="Affine la recherche côté Amazon. Vide = pas de filtre sur cette requête."
      >
        <UInput
          v-model="optionalSearch"
          icon="i-lucide-search"
          placeholder="Ex. Pokémon display, booster…"
          :disabled="loading || refreshing"
          size="lg"
          class="w-full min-w-0"
        />
      </UFormField>
      <UFormField
        class="min-w-0"
        label="Nombre de pages"
        description="Plage 1 à 50. Au-delà de quelques pages, l’actualisation prend plus de temps."
      >
        <UInput
          v-model="maxPagesInput"
          type="number"
          min="1"
          max="50"
          icon="i-lucide-layers"
          :disabled="loading || refreshing"
          size="lg"
          class="w-full min-w-0"
        />
      </UFormField>
    </div>

    <!-- Filtre local + actions -->
    <div
      class="border-default flex flex-col gap-4 border-t pt-4 sm:flex-row sm:flex-wrap sm:items-end sm:justify-between"
    >
      <div class="flex w-full min-w-0 flex-1 flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
        <UFormField
          class="min-w-0 flex-1 sm:max-w-md"
          label="Filtrer la liste"
          description="Filtre les invitations déjà chargées, sans relancer une récupération."
        >
          <UInput
            v-model="searchQuery"
            icon="i-lucide-filter"
            placeholder="Titre ou ASIN…"
            :loading="loading"
            size="md"
            class="w-full"
          />
        </UFormField>
        <UFormField label="Statut" description="Afficher uniquement les fiches dans cet état." class="w-full sm:w-auto">
          <USelect
            v-model="statusFilter"
            :items="statusSelectItems"
            value-key="value"
            class="w-full min-w-56 sm:w-auto"
            :disabled="totalLoaded === 0"
          />
        </UFormField>
      </div>
      <div class="flex flex-wrap items-center gap-3">
        <div class="flex items-center gap-2">
          <USwitch v-model="hideExpired" />
          <span class="text-highlighted text-sm">Masquer expirées</span>
        </div>
        <UButton
          color="primary"
          icon="i-lucide-refresh-cw"
          :loading="refreshing"
          :disabled="loading"
          @click="emit('refresh')"
        >
          Actualiser
        </UButton>
      </div>
    </div>

    <p v-if="!loading && totalLoaded > 0" class="text-muted text-xs">
      {{ resultCount }} affichée<span v-if="resultCount !== 1">s</span> sur {{ totalLoaded }}
      <span v-if="resultCount < totalLoaded">(filtres actifs)</span>
    </p>
  </div>
</template>

<script setup lang="ts">
import type { PropType, WritableComputedRef } from 'vue'
import type { AmazonStatusFilter, AmazonStatusSelectItem } from '~/types/amazonInvites'
import type { GoupixDexAmazonInvitesToolbarProps } from '~/types/GoupixDexAmazonInvitesToolbar'

const optionalSearch = defineModel<string>('optionalSearch', { required: true })
const maxPages = defineModel<number>('maxPages', { required: true })
const searchQuery = defineModel<string>('searchQuery', { required: true })
const hideExpired = defineModel<boolean>('hideExpired', { required: true })
const statusFilter = defineModel<AmazonStatusFilter>('statusFilter', { required: true })

/**
 * Toolbar props (loading flags, result counts, status select rows).
 */
const _props: GoupixDexAmazonInvitesToolbarProps = defineProps({
  loading: { type: Boolean, required: true },
  refreshing: { type: Boolean, required: true },
  resultCount: { type: Number, required: true },
  totalLoaded: { type: Number, required: true },
  statusSelectItems: {
    type: Array as PropType<AmazonStatusSelectItem[]>,
    required: true,
  },
})

const emit = defineEmits<{
  refresh: []
}>()

/**
 * Parses the pages input and updates the bound `maxPages` model.
 * @param raw - Raw value from the number input.
 */
function onMaxPagesInput(raw: string | number | null | undefined): void {
  const n = typeof raw === 'number' ? raw : Number(String(raw ?? '').replace(',', '.'))
  maxPages.value = Number.isFinite(n) ? Math.min(50, Math.max(1, Math.round(n))) : 2
}

/**
 * String bridge for `UInput type="number"` and numeric `maxPages` v-model.
 */
const maxPagesInput: WritableComputedRef<string> = computed({
  get: (): string => String(maxPages.value),
  set: (v: string): void => {
    onMaxPagesInput(v)
  },
})
</script>
