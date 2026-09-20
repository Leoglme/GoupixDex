<template>
  <GoupixDexDialogModal v-model:open="open" title="Ranger une carte" :description="placeLabel" width-class="max-w-2xl">
    <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
      <div class="relative min-w-0 flex-1">
        <UIcon
          name="i-lucide-search"
          class="text-muted pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2"
          aria-hidden
        />
        <input
          ref="searchRef"
          v-model="query"
          type="search"
          class="app-input pl-9"
          placeholder="Nom, numéro… (catalogue Pokémon)"
          autocomplete="off"
          @keydown.escape.stop
        />
      </div>
      <select
        v-if="setOptions.length > 1"
        v-model="setFilter"
        class="app-input shrink-0 sm:max-w-[13rem]"
        aria-label="Extension"
      >
        <option value="">Toutes les extensions</option>
        <option v-for="s in setOptions" :key="s" :value="s">{{ s }}</option>
      </select>
    </div>

    <p v-if="catalogSearching" class="text-muted mt-2 flex items-center gap-2 text-xs">
      <UIcon name="i-lucide-loader-2" class="size-3.5 animate-spin" aria-hidden />
      Recherche dans le catalogue…
    </p>
    <p v-else-if="query.trim().length >= catalogMinQuery" class="text-muted mt-2 text-xs">
      Résultats collection + catalogue officiel.
    </p>

    <div class="mt-4 max-h-[min(52vh,26rem)] overflow-y-auto pr-0.5">
      <p v-if="showEmptyHint" class="text-muted py-6 text-center text-sm leading-relaxed">
        Tape au moins {{ catalogMinQuery }} caractères pour chercher dans le catalogue Pokémon, ou ajoute des cartes
        depuis
        <NuxtLink to="/collection/add" class="font-medium text-(--app-accent) hover:underline" @click="open = false">
          ma collection
        </NuxtLink>
        .
      </p>
      <p v-else-if="results.length === 0" class="text-muted py-6 text-center text-sm">Aucune carte ne correspond.</p>
      <ul v-else class="grid grid-cols-3 gap-3 sm:grid-cols-4">
        <li v-for="c in results" :key="pickerItemKey(c)">
          <button type="button" class="group/c block w-full cursor-pointer text-left" @click="$emit('pick', c)">
            <div
              class="card-tile relative aspect-[63/88]"
              :class="c.source === 'catalog' ? 'ring-dashed ring-1 ring-(--app-line)' : ''"
            >
              <GoupixDexBinderCardImage v-if="c.image_url" :src="c.image_url" :alt="cardTitle(c)" />
              <div v-else class="flex h-full items-center justify-center bg-(--app-surface-2) text-(--app-faint)">
                <UIcon name="i-lucide-image-off" class="size-8" aria-hidden />
              </div>
              <span
                v-if="c.source === 'collection' && placedIds.has(c.collection_card_id)"
                class="tile-badge num bottom-1.5 left-1/2 z-10 -translate-x-1/2 !bg-black/75 whitespace-nowrap !text-white"
              >
                Déjà rangée
              </span>
              <span
                v-else-if="c.source === 'catalog'"
                class="tile-badge num top-1.5 left-1.5 z-10 !bg-(--app-surface-2)/95 !text-(--app-ink-soft)"
              >
                Catalogue
              </span>
              <span v-if="c.source === 'collection' && c.quantity > 1" class="tile-badge num top-1.5 right-1.5 z-10">
                ×{{ c.quantity }}
              </span>
            </div>
            <p class="mt-1.5 truncate text-xs font-medium group-hover/c:text-(--app-accent)">{{ cardTitle(c) }}</p>
            <p class="truncate text-[11px] text-(--app-faint)">{{ c.set_name }} · {{ cardLocalId(c) }}</p>
          </button>
        </li>
      </ul>
      <p v-if="results.length >= maxResults && hasMoreCollection" class="text-muted mt-3 text-center text-xs">
        {{ maxResults }} cartes affichées — affine la recherche pour en voir d'autres.
      </p>
    </div>
  </GoupixDexDialogModal>
</template>

<script setup lang="ts">
import { CATALOG_MIN_QUERY } from '~/composables/useBinderPickerResults'
import { PICKER_MAX } from '~/composables/useBinderPages'
import type { BinderPickerItem } from '~/types/binderPicker'
import { pickerItemKey } from '~/types/binderPicker'

const props = defineProps<{
  placeLabel?: string
  results: BinderPickerItem[]
  placedIds: Set<number>
  setOptions: string[]
  catalogSearching?: boolean
  hasCollectionCandidates?: boolean
}>()

defineEmits<{ pick: [BinderPickerItem] }>()

const open = defineModel<boolean>('open', { default: false })
const query = defineModel<string>('query', { default: '' })
const setFilter = defineModel<string>('setFilter', { default: '' })

const maxResults = PICKER_MAX
const catalogMinQuery = CATALOG_MIN_QUERY
const searchRef = ref<HTMLInputElement | null>(null)

const showEmptyHint = computed(
  () =>
    props.results.length === 0 &&
    !props.catalogSearching &&
    query.value.trim().length < catalogMinQuery &&
    !props.hasCollectionCandidates,
)

const hasMoreCollection = computed(() => props.hasCollectionCandidates ?? false)

function cardTitle(c: BinderPickerItem): string {
  return c.source === 'collection' ? c.card_name : c.card_name
}

function cardLocalId(c: BinderPickerItem): string {
  return c.source === 'collection' ? c.local_id : c.local_id
}

watch(open, (isOpen) => {
  if (isOpen) {
    nextTick(() => searchRef.value?.focus())
  }
})
</script>
