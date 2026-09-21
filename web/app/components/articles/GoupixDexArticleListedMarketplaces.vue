<template>
  <div class="inline-flex items-center justify-center gap-1" :title="tooltip" :aria-label="tooltip">
    <span
      v-if="showVinted"
      class="inline-flex size-5 items-center justify-center rounded-full ring-1 transition-colors"
      :class="
        row.published_on_vinted ? 'bg-[#09B1BA]/22 ring-[#09B1BA]' : 'bg-[var(--app-surface-2)] ring-[#09B1BA]/55'
      "
    >
      <UIcon name="i-simple-icons-vinted" class="size-3 text-[#09B1BA]" aria-hidden="true" />
    </span>
    <span
      v-if="showEbay"
      class="inline-flex size-5 items-center justify-center rounded-full ring-1 transition-colors"
      :class="row.published_on_ebay ? 'bg-[#86b817]/18 ring-[#86b817]' : 'bg-[var(--app-surface-2)] ring-[#86b817]/50'"
    >
      <span
        class="flex h-3 w-[1.125rem] items-center justify-center overflow-hidden rounded-[2px] bg-white/95 px-px shadow-[0_0_0_1px_rgba(255,255,255,0.35)]"
        aria-hidden="true"
      >
        <GoupixDexEbayLogoGradient tight class="h-2.5 w-full" />
      </span>
    </span>
    <span
      v-if="showLeboncoin"
      class="inline-flex size-5 items-center justify-center rounded-full ring-1 transition-colors"
      :class="
        row.published_on_leboncoin ? 'bg-[#FF6E14]/20 ring-[#FF6E14]' : 'bg-[var(--app-surface-2)] ring-[#FF6E14]/55'
      "
    >
      <GoupixDexLeboncoinMark class="size-3.5 rounded-[3px]" aria-hidden="true" />
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
