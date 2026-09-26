<template>
  <div class="inline-flex items-center justify-center gap-1.5" :title="tooltip" :aria-label="tooltip">
    <GoupixDexMarketplaceAppIcon v-if="showVinted" marketplace="vinted" :is-greyed-out="!row.published_on_vinted" />
    <GoupixDexMarketplaceAppIcon v-if="showEbay" marketplace="ebay" :is-greyed-out="!row.published_on_ebay" />
    <GoupixDexMarketplaceAppIcon
      v-if="showLeboncoin"
      marketplace="leboncoin"
      :is-greyed-out="!row.published_on_leboncoin"
    />
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
