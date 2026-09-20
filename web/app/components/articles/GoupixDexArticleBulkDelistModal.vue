<template>
  <GoupixDexDialogModal
    v-model:open="open"
    title="Retirer de la vente"
    :description="selectionLine"
    width-class="max-w-md"
  >
    <p class="mb-3 text-xs leading-relaxed text-[var(--app-ink-soft)]">
      Les fiches restent enregistrées (photos, description). Si plus aucune marketplace n’est active, l’article
      disparaît de « Mes articles » mais reste dans votre collection.
    </p>
    <div class="space-y-2">
      <button
        type="button"
        class="channel-row w-full cursor-pointer rounded-xl border px-3 py-2.5 text-left transition-colors outline-none focus:outline-none focus-visible:ring-2 focus-visible:ring-[#09B1BA]/55 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--app-surface)] disabled:cursor-not-allowed disabled:opacity-45"
        :class="pickVinted ? vintedRowActive : vintedRowIdle"
        :disabled="!vintedAvailable"
        :aria-pressed="pickVinted"
        aria-label="Vinted"
        @click="toggleVinted"
      >
        <span
          class="channel-row-check flex size-5 items-center justify-center rounded-md border transition-colors"
          :class="brandCheckboxClass('vinted', pickVinted)"
          aria-hidden="true"
        >
          <UIcon v-if="pickVinted" name="i-lucide-check" class="size-3.5" />
        </span>
        <span class="channel-row-body channel-row-body--vinted">
          <UIcon name="i-simple-icons-vinted" class="size-6 shrink-0 text-[#09B1BA]" aria-hidden="true" />
          <span class="channel-row-text">
            <span class="block text-sm font-semibold text-[#09B1BA]">Vinted</span>
            <span v-if="vintedHint" class="mt-0.5 block text-xs leading-snug text-[#09B1BA]/75">{{ vintedHint }}</span>
          </span>
        </span>
      </button>

      <button
        type="button"
        class="channel-row w-full cursor-pointer rounded-xl border px-3 py-2.5 text-left transition-colors outline-none focus:outline-none focus-visible:ring-2 focus-visible:ring-[#86b817]/55 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--app-surface)] disabled:cursor-not-allowed disabled:opacity-45"
        :class="pickEbay ? ebayRowActive : ebayRowIdle"
        :disabled="!ebayAvailable"
        :aria-pressed="pickEbay"
        aria-label="eBay"
        @click="toggleEbay"
      >
        <span
          class="channel-row-check flex size-5 items-center justify-center rounded-md border transition-colors"
          :class="brandCheckboxClass('ebay', pickEbay)"
          aria-hidden="true"
        >
          <UIcon v-if="pickEbay" name="i-lucide-check" class="size-3.5" />
        </span>
        <span class="channel-row-body">
          <GoupixDexEbayLogoGradient tight class="channel-mark-ebay shrink-0" aria-hidden="true" />
          <span v-if="ebayHint" class="channel-row-text text-muted text-xs leading-snug">{{ ebayHint }}</span>
        </span>
      </button>

      <button
        type="button"
        class="channel-row w-full rounded-xl border px-3 py-2.5 text-left transition-colors outline-none focus:outline-none focus-visible:ring-2 focus-visible:ring-[#FF6E14]/55 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--app-surface)]"
        :class="[
          pickLeboncoin ? leboncoinRowActive : leboncoinRowIdle,
          leboncoinAvailable ? 'cursor-pointer' : 'cursor-not-allowed opacity-45',
        ]"
        :aria-pressed="pickLeboncoin"
        :aria-disabled="!leboncoinAvailable"
        aria-label="Le Bon Coin"
        @click="toggleLeboncoin"
      >
        <span
          class="channel-row-check flex size-5 items-center justify-center rounded-md border transition-colors"
          :class="brandCheckboxClass('leboncoin', pickLeboncoin)"
          aria-hidden="true"
        >
          <UIcon v-if="pickLeboncoin" name="i-lucide-check" class="size-3.5" />
        </span>
        <span class="channel-row-body">
          <GoupixDexLeboncoinLogo class="channel-mark-lbc shrink-0" aria-hidden="true" />
          <span class="channel-row-text text-xs leading-snug text-[#FF6E14]/90">{{ leboncoinHint }}</span>
        </span>
      </button>

      <button
        type="button"
        class="channel-row mt-2 w-full cursor-pointer rounded-xl border border-dashed px-3 py-2.5 text-left transition-colors outline-none focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-accent)]/50 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--app-surface)] disabled:cursor-not-allowed disabled:opacity-45"
        :class="allChannelsActive ? allRowActive : allRowIdle"
        :disabled="!anyChannelAvailable"
        @click="toggleAllChannels"
      >
        <span
          class="channel-row-check flex size-5 items-center justify-center rounded-md border transition-colors"
          :class="brandCheckboxClass('all', allChannelsActive)"
          aria-hidden="true"
        >
          <UIcon v-if="allChannelsActive" name="i-lucide-check" class="size-3.5" />
        </span>
        <span class="channel-row-body">
          <span class="text-sm font-medium text-[var(--app-ink)]">Tout sélectionner</span>
        </span>
      </button>
    </div>

    <template #footer>
      <button type="button" class="dialog-btn-secondary" :disabled="loading" @click="close">Annuler</button>
      <button type="button" class="dialog-btn-danger" :disabled="loading || !canSubmit" @click="submit">
        <UIcon v-if="loading" name="i-lucide-loader-2" class="size-4 animate-spin" aria-hidden="true" />
        Lancer le retrait
      </button>
    </template>
  </GoupixDexDialogModal>
</template>

<script setup lang="ts">
import type { Ref } from 'vue'

type BrandKey = 'vinted' | 'ebay' | 'leboncoin' | 'all'

const props = defineProps<{
  articleCount: number
  vintedChannelEnabled: boolean
  isDesktopApp: boolean
  anyVintedListed: boolean
  anyEbayListed: boolean
  anyLeboncoinListed: boolean
  loading?: boolean
}>()

const open = defineModel<boolean>('open', { default: false })

const emit = defineEmits<{
  confirm: [payload: { vinted: boolean; ebay: boolean; leboncoin: boolean }]
}>()

const pickVinted: Ref<boolean> = ref(false)
const pickEbay: Ref<boolean> = ref(false)
const pickLeboncoin: Ref<boolean> = ref(false)

const vintedRowIdle = 'border-[#09B1BA]/30 bg-[#09B1BA]/8 hover:border-[#09B1BA]/45 hover:bg-[#09B1BA]/10'
const vintedRowActive = 'border-[#09B1BA]/55 bg-[#09B1BA]/14 ring-1 ring-[#09B1BA]/25'
const ebayRowIdle = 'border-[#86b817]/30 bg-[#86b817]/8 hover:border-[#86b817]/45 hover:bg-[#86b817]/10'
const ebayRowActive = 'border-[#86b817]/55 bg-[#86b817]/14 ring-1 ring-[#86b817]/30'
const leboncoinRowIdle = 'border-[#FF6E14]/35 bg-[#FF6E14]/10 hover:border-[#FF6E14]/50 hover:bg-[#FF6E14]/14'
const leboncoinRowActive = 'border-[#FF6E14]/60 bg-[#FF6E14]/16 ring-1 ring-[#FF6E14]/30'
const allRowIdle = 'border-[var(--app-line)] bg-[var(--app-surface)] hover:border-[var(--app-ink-soft)]'
const allRowActive = 'border-[var(--app-accent)]/40 bg-[var(--app-accent-soft)] !border-solid'

function brandCheckboxClass(brand: BrandKey, checked: boolean): string {
  if (!checked) {
    switch (brand) {
      case 'vinted':
        return 'border-[#09B1BA]/45 bg-[#09B1BA]/15'
      case 'ebay':
        return 'border-[#86b817]/45 bg-[#86b817]/12'
      case 'leboncoin':
        return 'border-[#FF6E14]/50 bg-[#FF6E14]/18'
      default:
        return 'border-[var(--app-line)] bg-[var(--app-surface-2)]'
    }
  }
  switch (brand) {
    case 'vinted':
      return 'border-[#09B1BA] bg-[#09B1BA] text-white'
    case 'ebay':
      return 'border-[#86b817] bg-[#86b817] text-[#1a1a1a]'
    case 'leboncoin':
      return 'border-[#FF6E14] bg-[#FF6E14] text-white'
    default:
      return 'border-[var(--app-accent)] bg-[var(--app-accent)] text-[var(--color-primary-950,#3c1408)]'
  }
}

const vintedAvailable = computed(() => props.anyVintedListed && props.vintedChannelEnabled && props.isDesktopApp)
const ebayAvailable = computed(() => props.anyEbayListed)
const leboncoinAvailable = computed(() => props.anyLeboncoinListed)

const anyChannelAvailable = computed(() => vintedAvailable.value || ebayAvailable.value || leboncoinAvailable.value)

const vintedHint = computed(() => {
  if (!props.anyVintedListed) {
    return 'Aucun article sélectionné n’est en ligne sur Vinted.'
  }
  if (!props.vintedChannelEnabled) {
    return 'Vinted désactivé dans les paramètres.'
  }
  if (!props.isDesktopApp) {
    return 'Application desktop requise.'
  }
  return ''
})

const ebayHint = computed(() => (!props.anyEbayListed ? 'Aucun article sélectionné n’est en ligne sur eBay.' : ''))

const leboncoinHint = computed(() =>
  !props.anyLeboncoinListed ? 'Aucun article sélectionné n’est sur Leboncoin.' : 'Retrait local GoupixDex.',
)

const selectionLine = computed(() => {
  const n = props.articleCount
  if (n <= 0) {
    return 'Choisissez les marketplaces à retirer.'
  }
  return `${n} article${n > 1 ? 's' : ''} sélectionné${n > 1 ? 's' : ''} — choisissez les canaux.`
})

const allChannelsActive = computed(() => {
  if (!anyChannelAvailable.value) {
    return false
  }
  if (vintedAvailable.value && !pickVinted.value) {
    return false
  }
  if (ebayAvailable.value && !pickEbay.value) {
    return false
  }
  if (leboncoinAvailable.value && !pickLeboncoin.value) {
    return false
  }
  return true
})

const canSubmit = computed(() => pickVinted.value || pickEbay.value || pickLeboncoin.value)

watch(
  () => open.value,
  (isOpen) => {
    if (!isOpen) {
      return
    }
    pickVinted.value = vintedAvailable.value
    pickEbay.value = ebayAvailable.value
    pickLeboncoin.value = leboncoinAvailable.value
  },
)

function toggleVinted() {
  if (vintedAvailable.value) {
    pickVinted.value = !pickVinted.value
  }
}

function toggleEbay() {
  if (ebayAvailable.value) {
    pickEbay.value = !pickEbay.value
  }
}

function toggleLeboncoin() {
  if (leboncoinAvailable.value) {
    pickLeboncoin.value = !pickLeboncoin.value
  }
}

function toggleAllChannels() {
  if (!anyChannelAvailable.value) {
    return
  }
  const turnOn = !allChannelsActive.value
  if (turnOn) {
    if (vintedAvailable.value) {
      pickVinted.value = true
    }
    if (ebayAvailable.value) {
      pickEbay.value = true
    }
    if (leboncoinAvailable.value) {
      pickLeboncoin.value = true
    }
    return
  }
  pickVinted.value = false
  pickEbay.value = false
  pickLeboncoin.value = false
}

function close() {
  open.value = false
}

function submit() {
  if (!canSubmit.value) {
    return
  }
  emit('confirm', {
    vinted: pickVinted.value,
    ebay: pickEbay.value,
    leboncoin: pickLeboncoin.value,
  })
}
</script>

<style scoped>
.channel-row {
  display: grid;
  grid-template-columns: 1.25rem minmax(0, 1fr);
  column-gap: 0.625rem;
  align-items: center;
  min-height: 2.75rem;
}

.channel-row-check {
  justify-self: start;
}

.channel-row-body {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: flex-start;
  gap: 0.5rem;
  text-align: left;
}

.channel-row-body--vinted {
  gap: 0.3125rem;
}

.channel-row-text {
  min-width: 0;
  text-align: left;
}

.channel-mark-ebay {
  display: block;
  height: 1.25rem;
  width: 3rem;
  max-width: none;
}

.channel-mark-lbc {
  display: block;
  height: 1.125rem;
  width: 4.25rem;
  max-width: none;
}
</style>
