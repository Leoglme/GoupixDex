<template>
  <span class="block min-w-0" :title="isDisabled && disabledReason ? disabledReason : undefined">
    <button
      type="button"
      class="box-border inline-flex h-9 w-full min-w-0 items-center justify-center gap-2 rounded-lg px-3.5 text-sm font-medium whitespace-nowrap transition-colors disabled:pointer-events-none disabled:opacity-50"
      :class="buttonClasses"
      :disabled="isDisabled || isLoading"
      @click="emit('click')"
    >
      <UIcon v-if="isLoading" name="i-lucide-loader-2" class="size-4 shrink-0 animate-spin" aria-hidden="true" />
      <span
        v-else-if="action === 'delist' && marketplace === 'ebay'"
        class="inline-flex h-5 w-12 shrink-0 items-center justify-start overflow-hidden"
        aria-hidden="true"
      >
        <GoupixDexEbayLogoGradient class="h-5 w-12 max-w-none" />
      </span>
      <UIcon
        v-else-if="action === 'delist' && marketplace === 'vinted'"
        name="i-simple-icons-vinted"
        class="size-5 shrink-0"
        aria-hidden="true"
      />
      <GoupixDexMarketplaceAppIcon v-else :marketplace="marketplace" class="size-5" />
      <span class="truncate">{{ label }}</span>
    </button>
  </span>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType } from 'vue'
import type {
  GoupixDexMarketplaceButtonAction,
  GoupixDexMarketplaceButtonProps,
} from '~/types/GoupixDexMarketplaceButton'
import type { Marketplace } from '~/types/Marketplace'
import { MARKETPLACE_NAMES } from '~/utils/marketplaces'

const props: GoupixDexMarketplaceButtonProps = defineProps({
  marketplace: {
    type: String as PropType<Marketplace>,
    required: true,
  },
  action: {
    type: String as PropType<GoupixDexMarketplaceButtonAction>,
    required: true,
  },
  isLoading: {
    type: Boolean,
    default: false,
  },
  isDisabled: {
    type: Boolean,
    default: false,
  },
  disabledReason: {
    type: String as PropType<string | null>,
    default: null,
  },
})

const emit = defineEmits<{
  click: []
}>()

const label: ComputedRef<string> = computed(() =>
  props.action === 'publish'
    ? `Publier sur ${MARKETPLACE_NAMES[props.marketplace]}`
    : `Retirer de ${MARKETPLACE_NAMES[props.marketplace]}`,
)

const buttonClasses: ComputedRef<string> = computed(() => {
  if (props.action === 'publish') {
    return 'border border-dashed border-[var(--app-line)] bg-transparent text-highlighted hover:bg-elevated/60'
  }
  if (props.marketplace === 'vinted') {
    return 'border border-[#09B1BA]/40 bg-[#09B1BA] text-white hover:bg-[#08a0a8] shadow-sm shadow-[#09B1BA]/20'
  }
  return 'border-default bg-elevated/80 text-highlighted hover:bg-elevated ring-default ring-1 ring-inset'
})
</script>
