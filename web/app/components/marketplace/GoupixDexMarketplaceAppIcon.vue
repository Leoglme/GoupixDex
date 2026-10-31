<template>
  <span
    class="flex shrink-0 items-center justify-center overflow-hidden transition"
    :class="[
      props.isSmall ? 'size-4.5 rounded' : 'size-6 rounded-md',
      TILE_CLASSES_BY_MARKETPLACE[props.marketplace],
      { 'opacity-40 grayscale': props.isGreyedOut },
    ]"
  >
    <UIcon
      v-if="props.marketplace === 'vinted'"
      name="i-simple-icons-vinted"
      class="text-white"
      :class="props.isSmall ? 'size-3' : 'size-4'"
      aria-hidden="true"
    />
    <GoupixDexEbayLogoGradient v-else-if="props.marketplace === 'ebay'" tight aria-hidden="true" />
    <GoupixDexLeboncoinMark v-else aria-hidden="true" />
  </span>
</template>

<script lang="ts" setup>
import type { PropType } from 'vue'
import type { GoupixDexMarketplaceAppIconProps } from '~/types/GoupixDexMarketplaceAppIcon'
import type { Marketplace } from '~/types/Marketplace'

const props: GoupixDexMarketplaceAppIconProps = defineProps({
  marketplace: {
    type: String as PropType<Marketplace>,
    required: true,
  },
  isGreyedOut: {
    type: Boolean,
    default: false,
  },
  isSmall: {
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
