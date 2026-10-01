<template>
  <li class="flex gap-3">
    <span class="mt-[0.7em] h-0.5 w-3 shrink-0 rounded-full bg-(--app-accent)" aria-hidden="true"></span>
    <p class="min-w-0">
      <strong class="text-highlighted font-semibold">{{ props.term }} </strong>
      <slot />
    </p>
  </li>
</template>

<script lang="ts" setup>
import type { GoupixDexLegalListItemProps } from '~/types/GoupixDexLegalListItem'

const props: GoupixDexLegalListItemProps = defineProps({
  term: {
    type: String,
    required: true,
  },
})
</script>
