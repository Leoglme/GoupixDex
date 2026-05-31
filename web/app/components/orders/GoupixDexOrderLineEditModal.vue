<template>
  <UModal v-model:open="open" :title="modalTitle" description="Corrigez les champs importés depuis le PDF Cardmarket.">
    <template #body>
      <form class="space-y-4" @submit.prevent="onSubmit">
        <UFormField label="Nom de la carte" name="pokemon_name" required>
          <UInput v-model="state.pokemon_name" class="w-full" autocomplete="off" />
        </UFormField>
        <div class="grid gap-4 sm:grid-cols-2">
          <UFormField label="Set" name="set_code" required>
            <UInput v-model="state.set_code" class="w-full" placeholder="m2a" autocomplete="off" />
          </UFormField>
          <UFormField label="N° carte" name="card_number" required>
            <UInput v-model="state.card_number" class="w-full" placeholder="206" autocomplete="off" />
          </UFormField>
          <UFormField label="Langue" name="language_code" required>
            <UInput v-model="state.language_code" class="w-full" placeholder="JP" maxlength="16" />
          </UFormField>
          <UFormField label="Condition" name="condition_label" required>
            <UInput v-model="state.condition_label" class="w-full" placeholder="NM" maxlength="32" />
          </UFormField>
          <UFormField label="Prix unitaire (€)" name="unit_price_eur" required>
            <UInput
              v-model="state.unit_price_eur"
              type="number"
              step="0.01"
              min="0"
              class="w-full"
              inputmode="decimal"
            />
          </UFormField>
          <UFormField label="Quantité" name="quantity" required>
            <UInput v-model.number="state.quantity" type="number" min="1" step="1" class="w-full" />
          </UFormField>
        </div>
        <p v-if="line?.articles?.length" class="text-muted text-xs">
          {{ line.articles.length }} article(s) lié(s) à cette ligne.
        </p>
        <div class="flex justify-end gap-2 pt-2">
          <UButton color="neutral" variant="subtle" type="button" :disabled="submitting" @click="open = false">
            Annuler
          </UButton>
          <UButton color="primary" type="submit" :loading="submitting"> Enregistrer </UButton>
        </div>
      </form>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import type { OrderDetailLine } from '~/types/Orders'

export interface OrderLineEditPayload {
  pokemon_name: string
  set_code: string
  card_number: string
  language_code: string
  condition_label: string
  unit_price_eur: number
  quantity: number
}

const open = defineModel<boolean>('open', { required: true })

const props = defineProps<{
  line: OrderDetailLine | null
  pokemonLabel: string
  submitting?: boolean
}>()

const emit = defineEmits<{
  submit: [payload: OrderLineEditPayload]
}>()

const state = reactive<OrderLineEditPayload>({
  pokemon_name: '',
  set_code: '',
  card_number: '',
  language_code: '',
  condition_label: '',
  unit_price_eur: 0,
  quantity: 1,
})

const modalTitle = computed(() => (props.line ? `Modifier la ligne — ${props.pokemonLabel}` : 'Modifier la ligne'))

watch(
  () => [open.value, props.line] as const,
  ([isOpen, line]) => {
    if (!isOpen || !line) {
      return
    }
    state.pokemon_name = props.pokemonLabel
    state.set_code = line.set_code ?? ''
    state.card_number = line.card_number ?? ''
    state.language_code = line.language_code ?? ''
    state.condition_label = line.condition_label ?? ''
    state.unit_price_eur = line.unit_price_eur
    state.quantity = line.quantity
  },
  { immediate: true },
)

function onSubmit(): void {
  emit('submit', { ...state })
}
</script>
