<template>
  <UDashboardPanel id="sealed-product-page">
    <template #header>
      <UDashboardNavbar title="Produit scellé">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="app-dashboard-page mx-auto w-full max-w-2xl">
        <GoupixDexBackLink to="/collection/produits" />
        <GoupixDexSealedProductDetailBody :sealed-id="id" @deleted="onDeleted" />
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
definePageMeta({ middleware: 'auth' })

useGoupixPageSeo('Produit scellé', 'Détail d’un produit scellé de votre collection et préparation de la mise en vente.')

const route = useRoute()

const id = computed<number>(() => Number(route.params.id))

/**
 * Retourne à la liste après suppression du produit.
 */
function onDeleted(): void {
  void navigateTo('/collection/produits')
}
</script>
