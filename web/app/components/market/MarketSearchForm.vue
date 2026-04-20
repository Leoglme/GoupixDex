<script setup lang="ts">
import type {
  ConditionFilter,
  GradedFilter,
  MarketSearchInput,
  SortOrder
} from '~/composables/useMarketSearch'

const props = defineProps<{
  loading?: boolean
  /** Number of matches returned by the last search (for display in submit button). */
  resultCount?: number | null
}>()

const emit = defineEmits<{
  submit: [input: MarketSearchInput]
}>()

const q = ref('')
const periodDays = ref<number>(30)
const condition = ref<ConditionFilter>('new')
const graded = ref<GradedFilter>('all')
const sort = ref<SortOrder>('relevance')
const frOnly = ref<boolean>(false)
const minPrice = ref<string>('')
const maxPrice = ref<string>('')
const limit = ref<number>(50)

const periodOptions = [
  { label: '7 derniers jours', value: 7 },
  { label: '14 derniers jours', value: 14 },
  { label: '30 derniers jours', value: 30 },
  { label: '60 derniers jours', value: 60 },
  { label: '90 derniers jours', value: 90 },
  { label: 'Sans limite', value: 0 }
]

const conditionOptions: { label: string, value: ConditionFilter }[] = [
  { label: 'Toutes', value: 'all' },
  { label: 'Neuf / scellé', value: 'new' },
  { label: 'Occasion', value: 'used' }
]

const gradedOptions: { label: string, value: GradedFilter }[] = [
  { label: 'Tous', value: 'all' },
  { label: 'Raw (non gradé)', value: 'raw' },
  { label: 'PSA', value: 'psa' },
  { label: 'CGC', value: 'cgc' },
  { label: 'BGS / Beckett', value: 'bgs' }
]

const sortOptions: { label: string, value: SortOrder }[] = [
  { label: 'Pertinence', value: 'relevance' },
  { label: 'Prix croissant', value: 'price_asc' },
  { label: 'Prix décroissant', value: 'price_desc' },
  { label: 'Plus récentes', value: 'newly_listed' }
]

const limitOptions = [
  { label: '25 résultats', value: 25 },
  { label: '50 résultats', value: 50 },
  { label: '100 résultats', value: 100 },
  { label: '200 résultats', value: 200 }
]

function parseNumber(value: string): number | null {
  const v = value.replace(',', '.').trim()
  if (!v) {
    return null
  }
  const n = Number(v)
  if (!Number.isFinite(n) || n < 0) {
    return null
  }
  return n
}

function submit() {
  const trimmed = q.value.trim()
  if (trimmed.length < 2) {
    return
  }
  emit('submit', {
    q: trimmed,
    periodDays: periodDays.value,
    condition: condition.value,
    graded: graded.value,
    sort: sort.value,
    frOnly: frOnly.value,
    minPrice: parseNumber(minPrice.value),
    maxPrice: parseNumber(maxPrice.value),
    limit: limit.value
  })
}

function applyExample(value: string) {
  q.value = value
  submit()
}
</script>

<template>
  <form class="space-y-4" @submit.prevent="submit">
    <UFormField label="Recherche" required>
      <UInput
        v-model="q"
        placeholder="Ex. ETB Évolutions Prismatiques FR, Pikachu VMAX 044 SWSH9…"
        icon="i-lucide-search"
        autofocus
        class="w-full"
        @keyup.enter="submit"
      />
    </UFormField>

    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <UFormField label="Période">
        <USelect
          v-model="periodDays"
          :items="periodOptions"
          value-key="value"
          label-key="label"
          class="w-full"
        />
      </UFormField>
      <UFormField label="État">
        <USelect
          v-model="condition"
          :items="conditionOptions"
          value-key="value"
          label-key="label"
          class="w-full"
        />
      </UFormField>
      <UFormField label="Grading">
        <USelect
          v-model="graded"
          :items="gradedOptions"
          value-key="value"
          label-key="label"
          class="w-full"
        />
      </UFormField>
      <UFormField label="Tri">
        <USelect
          v-model="sort"
          :items="sortOptions"
          value-key="value"
          label-key="label"
          class="w-full"
        />
      </UFormField>
    </div>

    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <UFormField label="Prix min (€)">
        <UInput
          v-model="minPrice"
          inputmode="decimal"
          placeholder="0"
          class="w-full"
        />
      </UFormField>
      <UFormField label="Prix max (€)">
        <UInput
          v-model="maxPrice"
          inputmode="decimal"
          placeholder="500"
          class="w-full"
        />
      </UFormField>
      <UFormField label="Nombre de résultats">
        <USelect
          v-model="limit"
          :items="limitOptions"
          value-key="value"
          label-key="label"
          class="w-full"
        />
      </UFormField>
      <UFormField label="Localisation">
        <div class="flex h-9 items-center rounded-md border border-default bg-elevated/40 px-3">
          <UCheckbox v-model="frOnly" label="France uniquement" />
        </div>
      </UFormField>
    </div>

    <div class="flex flex-wrap items-center gap-2">
      <UButton
        type="submit"
        color="primary"
        icon="i-lucide-search"
        :loading="loading"
        :disabled="q.trim().length < 2"
      >
        {{ props.resultCount != null && !loading ? `Relancer (${props.resultCount} résultats)` : 'Rechercher' }}
      </UButton>
      <span class="text-xs text-muted">Exemples :</span>
      <UButton
        v-for="example in ['Prismatic Evolutions Elite Trainer Box FR', 'Pikachu VMAX 188/185', 'Charizard UPC']"
        :key="example"
        size="xs"
        color="neutral"
        variant="soft"
        @click="applyExample(example)"
      >
        {{ example }}
      </UButton>
    </div>
  </form>
</template>
