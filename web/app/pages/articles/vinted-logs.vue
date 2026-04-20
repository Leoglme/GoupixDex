<script setup lang="ts">
/**
 * Ancienne URL : redirection vers le journal de mise en ligne (Vinted + eBay).
 */
definePageMeta({ middleware: 'auth' })
const route = useRoute()
onMounted(() => {
  void navigateTo({
    path: '/articles/listing-logs',
    query: { ...route.query },
    replace: true
  })
})
</script>

<template>
  <div class="hidden" aria-hidden="true" />
</template>
