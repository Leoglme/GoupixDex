<script setup lang="ts">
definePageMeta({ middleware: 'auth' })

await navigateTo('/articles', { replace: true })
</script>
