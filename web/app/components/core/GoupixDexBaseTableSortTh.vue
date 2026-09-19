<template>
  <th class="group/th border-b border-[var(--app-line)] px-3 py-2 md:px-4" :class="alignClass" scope="col">
    <button
      type="button"
      class="app-label inline-flex max-w-full cursor-pointer items-center gap-1 whitespace-nowrap transition-colors"
      :class="[
        align === 'right' && 'w-full justify-end',
        align === 'center' && 'w-full justify-center',
        active ? 'text-[var(--app-ink)]' : 'text-[var(--app-ink-soft)] hover:text-[var(--app-ink)]',
      ]"
      :title="title || label"
      :aria-label="sortAriaLabel"
      :aria-sort="active ? (direction === 'asc' ? 'ascending' : 'descending') : 'none'"
      @click="emit('sort')"
    >
      <span>{{ label }}</span>
      <UIcon
        v-if="active"
        :name="direction === 'asc' ? 'i-lucide-arrow-up' : 'i-lucide-arrow-down'"
        class="h-3 w-3 shrink-0 text-[var(--app-accent)]"
        aria-hidden="true"
      />
      <UIcon
        v-else
        name="i-lucide-arrow-up-down"
        class="h-3 w-3 shrink-0 opacity-0 transition-opacity group-hover/th:opacity-45"
        aria-hidden="true"
      />
    </button>
  </th>
</template>

<script lang="ts" setup>
import type {
  GoupixDexBaseTableAlign,
  GoupixDexBaseTableSortDirection,
  GoupixDexBaseTableSortThProps,
} from '~/types/GoupixDexBaseTable'
import type { ComputedRef } from 'vue'
import { computed } from 'vue'

const props: GoupixDexBaseTableSortThProps = defineProps({
  align: {
    type: String as () => GoupixDexBaseTableAlign,
    default: 'left',
  },
  label: {
    type: String,
    required: true,
  },
  active: {
    type: Boolean,
    default: false,
  },
  direction: {
    type: String as () => GoupixDexBaseTableSortDirection,
    default: 'desc',
  },
  title: {
    type: String,
    default: '',
  },
})

const emit = defineEmits<{
  sort: []
}>()

const alignClass: ComputedRef<string> = computed((): string => {
  if (props.align === 'center') return 'text-center'
  if (props.align === 'right') return 'text-right'
  return 'text-left'
})

const sortAriaLabel: ComputedRef<string> = computed((): string => {
  if (!props.active) {
    return `Trier par ${props.label}`
  }
  return `Trié par ${props.label}, ${props.direction === 'asc' ? 'croissant' : 'décroissant'}. Cliquer pour inverser.`
})
</script>
