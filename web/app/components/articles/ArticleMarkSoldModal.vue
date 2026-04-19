<script setup lang="ts">
import type { Article } from '~/composables/useArticles'

const props = defineProps<{
  article: Article | null
  /** When true, show eBay option; otherwise only Vinted (forced on save). */
  ebayEnabled: boolean
  loading?: boolean
}>()

const open = defineModel<boolean>('open', { default: false })
const toast = useToast()

const emit = defineEmits<{
  confirm: [payload: { soldPrice: number, saleSource: 'vinted' | 'ebay' }]
}>()

const saleSource = ref<'vinted' | 'ebay'>('vinted')
const priceInput = ref('')

watch(
  () => [open.value, props.article] as const,
  ([isOpen, a]) => {
    if (!isOpen || !a) {
      return
    }
    saleSource.value = 'vinted'
    const base = a.sell_price ?? a.purchase_price
    priceInput.value = base != null ? String(base) : ''
  }
)

function close() {
  open.value = false
}

function submit() {
  const raw = priceInput.value.replace(',', '.').trim()
  const n = Number(raw)
  if (Number.isNaN(n) || n < 0) {
    toast.add({ title: 'Montant invalide', description: 'Indiquez un prix en euros (≥ 0).', color: 'error' })
    return
  }
  const src = props.ebayEnabled ? saleSource.value : 'vinted'
  emit('confirm', { soldPrice: n, saleSource: src })
}
</script>

<template>
  <UModal
    v-model:open="open"
    title="Marquer comme vendu"
    description="Indiquez le canal et le montant réellement encaissé (€)."
  >
    <template #body>
      <div class="space-y-4">
        <UFormField
          v-if="ebayEnabled"
          label="Source de la vente"
        >
          <USelect
            v-model="saleSource"
            class="w-full"
            :items="[
              { label: 'Vinted', value: 'vinted' },
              { label: 'eBay', value: 'ebay' }
            ]"
            value-key="value"
            label-key="label"
          />
        </UFormField>
        <p
          v-else
          class="text-sm text-muted"
        >
          Vente enregistrée comme <span class="font-medium text-highlighted">Vinted</span>
          (eBay n'est pas activé dans vos paramètres).
        </p>

        <div class="space-y-1.5">
          <UFormField label="Prix réalisé (€)">
            <UInput
              v-model="priceInput"
              type="text"
              inputmode="decimal"
              class="w-full"
              placeholder="0,00"
            />
          </UFormField>
          <p class="text-xs text-muted">
            Prérempli avec le prix affiché sur l'annonce ; modifiez si besoin.
          </p>
        </div>

        <div class="flex justify-end gap-2 pt-2">
          <UButton
            color="neutral"
            variant="subtle"
            :disabled="loading"
            @click="close"
          >
            Annuler
          </UButton>
          <UButton
            :loading="loading"
            @click="submit"
          >
            Enregistrer
          </UButton>
        </div>
      </div>
    </template>
  </UModal>
</template>
