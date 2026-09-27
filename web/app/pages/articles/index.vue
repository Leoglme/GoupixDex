<template>
  <GoupixDexUnsoldArticlesView sale-status="forSale" />
</template>

<script setup lang="ts">
definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Mes articles — En ligne',
  'Annonces déjà en ligne sur Vinted ou eBay : suivi, mise à jour et vente dans GoupixDex.',
)
</script>
