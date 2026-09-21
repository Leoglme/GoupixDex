<template>
  <div class="inline-flex items-center justify-center gap-1.5" :title="tooltip" :aria-label="tooltip">
    <span
      v-if="showVinted"
      class="inline-flex size-6 items-center justify-center rounded-full ring-1 transition-opacity"
      :class="
        row.published_on_vinted
          ? 'bg-[#09B1BA]/15 opacity-100 ring-[#09B1BA]/45'
          : 'bg-transparent opacity-30 ring-[var(--app-line)]'
      "
    >
      <UIcon
        name="i-simple-icons-vinted"
        class="size-3.5"
        :class="row.published_on_vinted ? 'text-[#09B1BA]' : 'text-[var(--app-faint)]'"
        aria-hidden="true"
      />
    </span>
    <span
      v-if="showEbay"
      class="inline-flex size-6 items-center justify-center rounded-full ring-1 transition-opacity"
      :class="
        row.published_on_ebay
          ? 'bg-[#86b817]/12 opacity-100 ring-[#86b817]/45'
          : 'bg-transparent opacity-30 ring-[var(--app-line)]'
      "
    >
      <span
        class="text-[8px] leading-none font-extrabold tracking-tighter select-none"
        :class="row.published_on_ebay ? '' : 'opacity-50 grayscale'"
        aria-hidden="true"
      >
        <span class="text-[#E53238]">e</span><span class="text-[#0064D2]">b</span><span class="text-[#F5AF02]">a</span
        ><span class="text-[#86B817]">y</span>
      </span>
    </span>
    <span
      v-if="showLeboncoin"
      class="inline-flex size-6 items-center justify-center rounded-full ring-1 transition-opacity"
      :class="
        row.published_on_leboncoin
          ? 'bg-[#FF6E14]/15 opacity-100 ring-[#FF6E14]/50'
          : 'bg-transparent opacity-30 ring-[var(--app-line)]'
      "
    >
      <span
        class="text-[11px] leading-none font-extrabold select-none"
        :class="row.published_on_leboncoin ? 'text-[#FF6E14]' : 'text-[var(--app-faint)]'"
        aria-hidden="true"
      >
        L
      </span>
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
