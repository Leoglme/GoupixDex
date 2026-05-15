<template>
  <div class="text-muted p-8 text-center text-sm">Redirection vers le catalogue…</div>
</template>

<script setup lang="ts">
definePageMeta({ middleware: 'auth' })

/** Ancienne URL : la page catalogue vit désormais sous ``/articles/catalog``. */
await navigateTo('/articles/catalog', { replace: true })
</script>
