<script setup lang="ts">
defineProps<{
  title: string
  value: string | number
  icon?: string
  description?: string
}>()
</script>

<template>
  <UPageCard
    :icon="icon"
    :title="title"
    variant="subtle"
    :ui="{
      container: 'gap-y-1.5',
      wrapper: 'items-start',
      leading: 'p-2.5 rounded-full bg-primary/10 ring ring-inset ring-primary/25 flex-col',
      title: 'font-normal text-muted text-xs uppercase'
    }"
  >
    <div class="text-2xl font-semibold text-highlighted">
      {{ value }}
    </div>
    <p v-if="description" class="text-xs text-muted">
      {{ description }}
    </p>
  </UPageCard>
</template>
