<template>
  <span
    class="flex size-6 shrink-0 items-center justify-center overflow-hidden rounded-md transition"
    :class="[TILE_CLASSES_BY_MARKETPLACE[marketplace], { 'opacity-40 grayscale': isGreyedOut }]"
  >
    <UIcon v-if="marketplace === 'vinted'" name="i-simple-icons-vinted" class="size-4 text-white" aria-hidden="true" />
    <GoupixDexEbayLogoGradient v-else-if="marketplace === 'ebay'" tight aria-hidden="true" />
    <GoupixDexLeboncoinMark v-else aria-hidden="true" />
  </span>
</template>

<script lang="ts" setup>
import type { PropType } from 'vue'
import type { Marketplace } from '~/types/Marketplace'

defineProps({
  marketplace: {
    type: String as PropType<Marketplace>,
    required: true,
  },
  isGreyedOut: {
    type: Boolean,
    default: false,
  },
})

const TILE_CLASSES_BY_MARKETPLACE: Record<Marketplace, string> = {
  vinted: 'bg-linear-to-tr from-[#186E72] via-[#2E9599] to-[#4CB6BA]',
  ebay: 'bg-white px-0.5',
  leboncoin: '',
}
</script>
