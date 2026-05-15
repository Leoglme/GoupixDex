<template>
  <div class="space-y-3">
    <article
      v-for="i in count"
      :key="i"
      class="border-default bg-elevated/30 flex items-center gap-3 rounded-xl border p-3 sm:gap-4 sm:p-4"
    >
      <div class="bg-muted/40 size-10 shrink-0 animate-pulse rounded-full sm:size-12" />
      <div class="bg-muted/40 size-16 shrink-0 animate-pulse rounded-lg sm:size-20" />
      <div class="min-w-0 flex-1 space-y-2">
        <div class="bg-muted/40 h-3 w-3/4 animate-pulse rounded" />
        <div class="bg-muted/40 h-3 w-1/2 animate-pulse rounded" />
        <div class="flex gap-3">
          <div class="bg-muted/30 h-2.5 w-16 animate-pulse rounded" />
          <div class="bg-muted/30 h-2.5 w-20 animate-pulse rounded" />
        </div>
      </div>
      <div class="flex shrink-0 flex-col items-end gap-2">
        <div class="bg-muted/40 h-4 w-20 animate-pulse rounded" />
        <div class="bg-muted/30 h-2.5 w-14 animate-pulse rounded" />
      </div>
    </article>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ count?: number }>(), { count: 6 })
</script>
