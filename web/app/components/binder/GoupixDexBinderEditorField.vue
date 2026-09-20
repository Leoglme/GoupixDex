<template>
  <UFormField :label="label" :hint="hint" class="w-full">
    <slot />
  </UFormField>
</template>

<script setup lang="ts">
defineProps<{
  label: string
  hint?: string
}>()
</script>
