<template>
  <tr
    class="group border-b border-[var(--app-line-soft)] transition-colors last:border-b-0 hover:bg-[var(--app-surface-2)]/60"
    v-bind="$attrs"
  >
    <slot />
  </tr>
</template>

<script lang="ts" setup>
defineOptions({ inheritAttrs: false })
</script>
