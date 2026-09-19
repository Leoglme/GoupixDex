<template>
  <div class="flex flex-col gap-3">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div class="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row sm:items-center sm:gap-2">
        <UInput
          v-model="searchQuery"
          icon="i-lucide-search"
          placeholder="Recherche Amazon (Actualiser)…"
          :disabled="refreshing"
          size="md"
          class="w-full min-w-0 sm:max-w-md sm:flex-1"
        />
        <div class="flex shrink-0 items-center gap-2">
          <UInput
            v-model="maxItemsInput"
            type="number"
            min="1"
            max="500"
            :disabled="loading || refreshing"
            size="md"
            class="w-20 tabular-nums"
            aria-label="Nombre maximum de produits à récupérer"
          />
          <span class="text-muted text-xs font-medium whitespace-nowrap">produits max</span>
        </div>
      </div>

      <div class="flex shrink-0 flex-wrap items-center justify-end gap-2 sm:pl-4">
        <USelect
          v-model="statusFilter"
          :items="statusSelectItems"
          value-key="value"
          class="w-full min-w-56 sm:w-auto"
          :disabled="totalLoaded === 0"
          size="md"
        />
        <UButton
          color="primary"
          icon="i-lucide-refresh-cw"
          class="shrink-0"
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
      <span v-if="resultCount < totalLoaded">(filtre actif)</span>
    </p>
  </div>
</template>

<script setup lang="ts">
import type { WritableComputedRef } from 'vue'
import type { AmazonStatusFilter } from '~/types/amazonInvites'
import type { GoupixDexAmazonInvitesToolbarProps } from '~/types/GoupixDexAmazonInvitesToolbar'
import { clampMaxItems } from '~/utils/amazonInvitesScanLimit'

const maxItems = defineModel<number>('maxItems', { required: true })
const searchQuery = defineModel<string>('searchQuery', { required: true })
const statusFilter = defineModel<AmazonStatusFilter>('statusFilter', { required: true })

defineProps<GoupixDexAmazonInvitesToolbarProps>()

const emit = defineEmits<{
  refresh: []
}>()

function onMaxItemsInput(raw: string | number | null | undefined): void {
  const n = typeof raw === 'number' ? raw : Number(String(raw ?? '').replace(',', '.'))
  maxItems.value = clampMaxItems(n)
}

const maxItemsInput: WritableComputedRef<string> = computed({
  get: (): string => String(maxItems.value),
  set: (v: string): void => {
    onMaxItemsInput(v)
  },
})
</script>
