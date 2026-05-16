<template>
  <div class="text-muted p-8 text-center text-sm">Redirection vers le catalogue…</div>
</template>

<script setup lang="ts">
definePageMeta({ middleware: 'auth' })

/** Le catalogue est désormais piloté par ``Ma Collection`` (``/collection/add``). */
await navigateTo('/collection/add', { replace: true })
</script>
