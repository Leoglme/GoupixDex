<template>
  <div class="inline-flex items-center justify-center gap-1.5" :title="tooltip" :aria-label="tooltip">
    <span
      v-if="showVinted"
      class="flex size-6 items-center justify-center overflow-hidden rounded-md bg-linear-to-tr from-[#186E72] via-[#2E9599] to-[#4CB6BA] transition"
      :class="{ 'opacity-40 grayscale': !row.published_on_vinted }"
    >
      <UIcon name="i-simple-icons-vinted" class="size-4 text-white" aria-hidden="true" />
    </span>
    <span
      v-if="showEbay"
      class="flex size-6 items-center justify-center overflow-hidden rounded-md bg-white px-0.5 transition"
      :class="{ 'opacity-40 grayscale': !row.published_on_ebay }"
    >
      <GoupixDexEbayLogoGradient tight aria-hidden="true" />
    </span>
    <span
      v-if="showLeboncoin"
      class="flex size-6 overflow-hidden rounded-md transition"
      :class="{ 'opacity-40 grayscale': !row.published_on_leboncoin }"
    >
      <GoupixDexLeboncoinMark aria-hidden="true" />
    </span>
  </div>
</template>

<script setup lang="ts">
import type { Article } from '~/composables/useArticles'

const props = withDefaults(
  defineProps<{
    row: Pick<Article, 'published_on_vinted' | 'published_on_ebay' | 'published_on_leboncoin'>
    showVinted?: boolean
    showEbay?: boolean
    showLeboncoin?: boolean
  }>(),
  {
    showVinted: true,
    showEbay: true,
    showLeboncoin: true,
  },
)

const tooltip = computed(() => {
  const parts: string[] = []
  if (props.showVinted) {
    parts.push(props.row.published_on_vinted ? 'Vinted : en ligne' : 'Vinted : non publié')
  }
  if (props.showEbay) {
    parts.push(props.row.published_on_ebay ? 'eBay : en ligne' : 'eBay : non publié')
  }
  if (props.showLeboncoin) {
    parts.push(props.row.published_on_leboncoin ? 'Leboncoin : en ligne' : 'Leboncoin : non publié')
  }
  return parts.join(' · ')
})
</script>
