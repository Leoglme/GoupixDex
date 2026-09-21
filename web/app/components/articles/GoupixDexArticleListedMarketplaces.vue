<template>
  <div class="inline-flex items-center justify-center gap-1.5" :title="tooltip" :aria-label="tooltip">
    <span
      v-if="showVinted"
      class="inline-flex size-7 items-center justify-center rounded-full ring-2 transition-colors"
      :class="
        row.published_on_vinted ? 'bg-[#09B1BA]/25 ring-[#09B1BA]' : 'bg-[var(--app-surface-2)] ring-[#09B1BA]/70'
      "
    >
      <UIcon name="i-simple-icons-vinted" class="size-4 text-[#09B1BA]" aria-hidden="true" />
    </span>
    <span
      v-if="showEbay"
      class="inline-flex size-7 items-center justify-center rounded-full ring-2 transition-colors"
      :class="row.published_on_ebay ? 'bg-[#86b817]/20 ring-[#86b817]' : 'bg-[var(--app-surface-2)] ring-[#86b817]/65'"
    >
      <span class="text-[9px] leading-none font-black tracking-tighter select-none" aria-hidden="true">
        <span class="text-[#E53238]">e</span><span class="text-[#0064D2]">b</span><span class="text-[#F5AF02]">a</span
        ><span class="text-[#86B817]">y</span>
      </span>
    </span>
    <span
      v-if="showLeboncoin"
      class="inline-flex size-7 items-center justify-center rounded-full ring-2 transition-colors"
      :class="
        row.published_on_leboncoin ? 'bg-[#FF6E14]/25 ring-[#FF6E14]' : 'bg-[var(--app-surface-2)] ring-[#FF6E14]/70'
      "
    >
      <span class="text-xs leading-none font-black text-[#FF6E14] select-none" aria-hidden="true">L</span>
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
