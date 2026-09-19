<template>
  <button
    type="button"
    class="box-border inline-flex h-9 w-full min-w-0 items-center justify-center gap-2 rounded-lg px-3.5 text-sm font-medium whitespace-nowrap transition-colors disabled:pointer-events-none disabled:opacity-50"
    :class="marketplace === 'ebay' ? ebayClasses : vintedClasses"
    :disabled="disabled || loading"
    @click="emit('click')"
  >
    <span v-if="loading" class="inline-flex size-5 shrink-0 items-center justify-center" aria-hidden="true">
      <UIcon name="i-lucide-loader-2" class="size-4 animate-spin" />
    </span>
    <span
      v-else-if="marketplace === 'ebay'"
      class="inline-flex h-5 w-12 shrink-0 items-center justify-start overflow-hidden"
      aria-hidden="true"
    >
      <GoupixDexEbayLogoGradient class="h-5 w-12 max-w-none" />
    </span>
    <UIcon v-else name="i-simple-icons-vinted" class="size-5 shrink-0" aria-hidden="true" />
    <span class="whitespace-nowrap">{{ label }}</span>
  </button>
</template>

<script setup lang="ts">
type Marketplace = 'ebay' | 'vinted'

const props = withDefaults(
  defineProps<{
    marketplace: Marketplace
    loading?: boolean
    disabled?: boolean
  }>(),
  {
    loading: false,
    disabled: false,
  },
)

const emit = defineEmits<{
  click: []
}>()

const label = computed(() => (props.marketplace === 'ebay' ? 'Retirer de eBay' : 'Retirer de Vinted'))

const ebayClasses = 'border-default bg-elevated/80 text-highlighted hover:bg-elevated ring-default ring-1 ring-inset'

const vintedClasses =
  'border border-[#09B1BA]/40 bg-[#09B1BA] text-white hover:bg-[#08a0a8] shadow-sm shadow-[#09B1BA]/20'
</script>
