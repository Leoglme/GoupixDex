<template>
  <UDashboardPanel id="collection-card-page">
    <template #header>
      <UDashboardNavbar title="Carte de la collection">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton to="/collection" color="neutral" variant="ghost" icon="i-lucide-arrow-left"> Ma collection </UButton>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="app-dashboard-page mx-auto w-full max-w-2xl">
        <GoupixDexCollectionCardDetailBody :card-id="id" @deleted="onDeleted" />
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Carte de collection',
  'Détail d’une carte de votre collection Pokémon et préparation de la mise en vente.',
)

const route = useRoute()

const id = computed<number>(() => Number(route.params.id))

/**
 * Retourne à la liste après suppression de la carte.
 */
function onDeleted(): void {
  void navigateTo('/collection')
}
</script>
