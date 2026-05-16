<template>
  <div class="text-muted p-8 text-center text-sm">Redirection vers le catalogue Pokémon…</div>
</template>

<script setup lang="ts">
definePageMeta({ middleware: 'auth' })

/**
 * Le « Catalogue Pokémon » a été refactoré dans le flux ``Ma Collection`` :
 * - ``/collection`` : binder personnel.
 * - ``/collection/add`` : picker TCGdex (séries → sets → cartes).
 * - ``/collection/{id}`` : préremplir un article pour la mise en vente.
 */
await navigateTo('/collection/add', { replace: true })
</script>
