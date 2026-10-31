<template>
  <a
    :href="`/articles/${props.articleId}`"
    class="group flex w-full items-center gap-3 py-2.5 first:pt-0 last:pb-0"
    @click="openArticleFromClick(props.articleId, $event)"
  >
    <span class="bg-muted/20 relative aspect-[63/88] w-10 shrink-0 overflow-hidden rounded">
      <img
        v-if="props.imageUrl"
        :src="props.imageUrl"
        :alt="props.title"
        loading="lazy"
        decoding="async"
        class="absolute inset-0 size-full object-cover"
      />
      <span
        v-else
        class="absolute inset-0 flex items-center justify-center text-[11px] font-semibold text-(--app-ink-soft)"
      >
        {{ (props.pokemonName || props.title).slice(0, 2).toUpperCase() }}
      </span>
    </span>
    <span class="min-w-0 flex-1">
      <span class="text-highlighted block truncate text-sm font-medium group-hover:underline">{{ props.title }}</span>
      <span class="text-muted mt-0.5 flex min-w-0 items-center gap-1.5 text-xs">
        <slot name="subtitle" />
      </span>
    </span>
    <span class="shrink-0 text-right tabular-nums">
      <slot name="trailing" />
    </span>
  </a>
</template>

<script lang="ts" setup>
import type { PropType } from 'vue'
import type { GoupixDexDashboardArticleRowProps } from '~/types/GoupixDexDashboardArticleRow'

const props: GoupixDexDashboardArticleRowProps = defineProps({
  articleId: {
    type: Number,
    required: true,
  },
  title: {
    type: String,
    required: true,
  },
  pokemonName: {
    type: String as PropType<string | null>,
    default: null,
  },
  imageUrl: {
    type: String as PropType<string | null>,
    default: null,
  },
})

const { openArticleFromClick } = useOpenArticleDrawer()
</script>
