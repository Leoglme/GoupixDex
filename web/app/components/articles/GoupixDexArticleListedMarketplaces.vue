<template>
  <div class="inline-flex items-center justify-center gap-1" :title="tooltip" :aria-label="tooltip">
    <span
      v-if="showVinted"
      class="inline-flex size-6 items-center justify-center rounded-full ring-1 transition-opacity"
      :class="
        row.published_on_vinted
          ? 'bg-[#09B1BA]/15 opacity-100 ring-[#09B1BA]/45'
          : 'bg-transparent opacity-35 ring-[var(--app-line)]'
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
          ? 'bg-[#86b817]/12 opacity-100 ring-[#86b817]/40'
          : 'bg-transparent opacity-35 ring-[var(--app-line)]'
      "
    >
      <GoupixDexEbayLogoGradient class="h-2.5 w-6 max-w-none opacity-90" aria-hidden="true" />
    </span>
    <span
      v-if="showLeboncoin"
      class="inline-flex size-6 items-center justify-center rounded-full ring-1 transition-opacity"
      :class="
        row.published_on_leboncoin
          ? 'bg-[#FF6E14]/12 opacity-100 ring-[#FF6E14]/45'
          : 'bg-transparent opacity-35 ring-[var(--app-line)]'
      "
    >
      <GoupixDexLeboncoinLogo class="h-2 w-auto max-w-[1.35rem]" aria-hidden="true" />
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
