<script setup lang="ts">
definePageMeta({ middleware: 'auth' })

/** Ancienne URL : la page catalogue vit désormais sous ``/articles/catalog``. */
await navigateTo('/articles/catalog', { replace: true })
</script>

<template>
  <div class="p-8 text-center text-sm text-muted">
    Redirection vers le catalogue…
  </div>
</template>
