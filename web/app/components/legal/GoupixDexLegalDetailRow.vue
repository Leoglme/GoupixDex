<template>
  <div
    class="grid gap-0.5 border-b border-(--app-line-soft) py-3 last:border-b-0 sm:grid-cols-[10rem_minmax(0,1fr)] sm:gap-4"
  >
    <dt class="app-label pt-1">{{ props.label }}</dt>
    <dd class="text-highlighted min-w-0 break-words tabular-nums"><slot /></dd>
  </div>
</template>

<script lang="ts" setup>
import type { GoupixDexLegalDetailRowProps } from '~/types/GoupixDexLegalDetailRow'

const props: GoupixDexLegalDetailRowProps = defineProps({
  label: {
    type: String,
    required: true,
  },
})
</script>
