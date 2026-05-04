<template>
  <div class="hidden" aria-hidden="true" />
</template>

<script setup lang="ts">
/**
 * Legacy URL: redirects to the listing log page (Vinted + eBay).
 */
definePageMeta({ middleware: 'auth' })
const route = useRoute()
onMounted(() => {
  void navigateTo({
    path: '/articles/listing-logs',
    query: { ...route.query },
    replace: true,
  })
})
</script>
