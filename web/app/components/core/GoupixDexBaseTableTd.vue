<template>
  <td class="px-4 py-3" :class="alignClass" :data-label="label || undefined" v-bind="$attrs">
    <slot />
  </td>
</template>

<script lang="ts" setup>
import type { GoupixDexBaseTableAlign, GoupixDexBaseTableTdProps } from '~/types/GoupixDexBaseTable'
import type { ComputedRef } from 'vue'
import { computed } from 'vue'

const props: GoupixDexBaseTableTdProps = defineProps({
  align: {
    type: String as () => GoupixDexBaseTableAlign,
    default: 'left',
  },
  label: {
    type: String,
    default: '',
  },
})

const alignClass: ComputedRef<string> = computed((): string => {
  if (props.align === 'center') return 'text-center'
  if (props.align === 'right') return 'text-right'
  return 'text-left'
})
</script>
