<template>
  <GoupixDexDialogModal v-model:open="open" :title="modalTitle" :description="selectionLine" width-class="max-w-md">
    <p class="mb-4 text-xs leading-relaxed text-[var(--app-ink-soft)]">
      {{ bodyText }}
    </p>

    <label
      v-if="mode === 'restore-sale' && anyVintedListed"
      class="flex cursor-pointer items-start gap-2.5 rounded-xl border border-[var(--app-line)] bg-[var(--app-surface-2)]/50 px-3 py-3"
    >
      <input v-model="renewVinted" type="checkbox" class="mt-0.5 size-4 shrink-0 accent-[var(--app-accent)]" />
      <span class="text-xs leading-snug text-[var(--app-ink-soft)]">
        <span class="font-medium text-[var(--app-ink)]">Retirer l’ancienne annonce Vinted d’abord</span>
        — une annonce Vinted est encore enregistrée pour au moins une fiche ; le worker desktop la supprime avant
        republication.
      </span>
    </label>

    <template #footer>
      <button type="button" class="dialog-btn-primary w-full" :disabled="loading" @click="submit">
        <UIcon v-if="loading" name="i-lucide-loader-2" class="size-4 animate-spin" aria-hidden="true" />
        Continuer vers les fiches
      </button>
    </template>
  </GoupixDexDialogModal>
</template>

<script setup lang="ts">
import type { BulkRelistModalMode } from '~/utils/articleSaleState'

const props = defineProps<{
  articleCount: number
  mode: BulkRelistModalMode
  anyVintedListed: boolean
  loading?: boolean
}>()

const open = defineModel<boolean>('open', { default: false })

const emit = defineEmits<{
  confirm: [payload: { renewVinted: boolean; mode: BulkRelistModalMode }]
}>()

const renewVinted = ref(true)

const modalTitle = computed(() => (props.mode === 'vinted-renew' ? 'Relister' : 'Remettre en vente'))

const bodyText = computed(() => {
  if (props.mode === 'vinted-renew') {
    return 'Si une annonce Vinted est encore active, l’application desktop la retire d’abord. Vous arrivez ensuite sur chaque fiche préremplie : ajustez le prix si besoin, puis choisissez les marketplaces (Vinted, eBay, Le Bon Coin plus tard). Rien n’est publié sans votre validation.'
  }
  return 'Ces fiches avaient été retirées de la vente sur toutes les marketplaces. Même parcours : fiche préremplie, prix, puis choix des canaux avant publication.'
})

const selectionLine = computed(() => {
  const n = props.articleCount
  if (n <= 0) {
    return 'Préparez la republication.'
  }
  return `${n} article${n > 1 ? 's' : ''} sélectionné${n > 1 ? 's' : ''}.`
})

watch(
  () => open.value,
  (isOpen) => {
    if (isOpen) {
      renewVinted.value = props.anyVintedListed
    }
  },
)

function submit() {
  emit('confirm', {
    mode: props.mode,
    renewVinted: props.mode === 'vinted-renew' || (renewVinted.value && props.anyVintedListed),
  })
}
</script>
