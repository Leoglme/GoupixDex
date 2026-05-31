<template>
  <UModal
    v-model:open="open"
    title="Lignes liées à des articles"
    description="Ces lignes diffèrent du PDF mais ont des articles GoupixDex liés. Cochez celles à mettre à jour quand même."
  >
    <template #body>
      <div class="max-h-[min(60vh,24rem)] space-y-3 overflow-y-auto">
        <div v-for="item in pending" :key="item.line_index" class="border-default rounded-lg border p-3 text-sm">
          <label class="flex cursor-pointer items-start gap-3">
            <UCheckbox v-model="selected[item.line_index]!" class="mt-0.5" />
            <span class="min-w-0 flex-1 space-y-2">
              <span class="text-highlighted block font-medium">
                Ligne #{{ item.line_index + 1 }}
                <span class="text-muted font-normal"> · {{ item.linked_article_count }} article(s) lié(s) </span>
              </span>
              <span class="grid gap-2 sm:grid-cols-2">
                <span class="block">
                  <span class="text-muted text-xs uppercase">Actuel</span>
                  <span class="text-highlighted mt-0.5 block">
                    {{ formatSnapshot(item.current) }}
                  </span>
                </span>
                <span class="block">
                  <span class="text-muted text-xs uppercase">PDF</span>
                  <span class="text-primary mt-0.5 block">
                    {{ formatSnapshot(item.from_pdf) }}
                  </span>
                </span>
              </span>
            </span>
          </label>
        </div>
      </div>
      <div class="mt-4 flex flex-wrap justify-end gap-2">
        <UButton color="neutral" variant="subtle" :disabled="submitting" @click="onIgnore"> Ignorer </UButton>
        <UButton color="primary" :loading="submitting" :disabled="!anySelected" @click="onConfirm">
          Appliquer la sélection
        </UButton>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import type { OrderReimportLineDiff, OrderReimportLineSnapshot } from '~/types/Orders'

const open = defineModel<boolean>('open', { required: true })

const props = defineProps<{
  pending: OrderReimportLineDiff[]
  submitting?: boolean
}>()

const emit = defineEmits<{
  confirm: [lineIndexes: number[]]
  ignore: []
}>()

const selected = ref<Record<number, boolean>>({})

watch(
  () => props.pending,
  (items) => {
    selected.value = Object.fromEntries(items.map((item) => [item.line_index, false]))
  },
  { immediate: true },
)

const anySelected = computed(() => props.pending.some((p) => selected.value[p.line_index]))

function formatSnapshot(snap: OrderReimportLineSnapshot): string {
  const name = 'pokemon_name' in snap && snap.pokemon_name ? snap.pokemon_name : (snap.pokemon_key ?? '—')
  return `${name} · ${snap.set_code ?? '—'} · ${snap.card_number ?? '—'} · ${snap.language_code ?? '—'} · ${snap.condition_label ?? '—'} · ${snap.unit_price_eur} €`
}

function onConfirm(): void {
  const indexes = props.pending.filter((p) => selected.value[p.line_index]).map((p) => p.line_index)
  emit('confirm', indexes)
}

function onIgnore(): void {
  open.value = false
  emit('ignore')
}
</script>
