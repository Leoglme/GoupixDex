<script setup lang="ts">
/** Ancienne URL (OAuth eBay, liens profonds) → page Paramètres unifiée. */
definePageMeta({ middleware: 'auth' })

const route = useRoute()

await navigateTo(
  {
    path: '/settings',
    query: route.query,
    hash: route.hash,
  },
  { replace: true },
)
</script>
