<template>
  <GoupixDexUnsoldArticlesView sale-status="withdrawn" />
</template>

<script setup lang="ts">
definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Mes articles — Retirés',
  'Fiches retirées de toutes les marketplaces, prêtes à être remises en vente depuis GoupixDex.',
)
</script>
