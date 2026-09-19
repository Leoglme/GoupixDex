<template>
  <th
    class="app-label border-b border-[var(--app-line)] px-3 py-2.5 whitespace-nowrap md:px-4"
    :class="[alignClass, srOnly && 'sr-only']"
    v-bind="$attrs"
  >
    <slot />
  </th>
</template>

<script lang="ts" setup>
import type { GoupixDexBaseTableAlign, GoupixDexBaseTableThProps } from '~/types/GoupixDexBaseTable'
import type { ComputedRef } from 'vue'
import { computed } from 'vue'

const props: GoupixDexBaseTableThProps = defineProps({
  align: {
    type: String as () => GoupixDexBaseTableAlign,
    default: 'left',
  },
  srOnly: {
    type: Boolean,
    default: false,
  },
})

const alignClass: ComputedRef<string> = computed((): string => {
  if (props.align === 'center') return 'text-center'
  if (props.align === 'right') return 'text-right'
  return 'text-left'
})
</script>
