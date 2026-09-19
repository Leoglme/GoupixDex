<template>
  <UDashboardPanel id="articles-stock">
    <template #header>
      <UDashboardNavbar>
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #title>
          <span class="app-label flex items-center gap-1.5 !text-[0.65rem]">
            <UIcon name="i-lucide-flame" class="h-3 w-3 text-(--app-accent)" />
            Vente
          </span>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="w-full space-y-3 px-2 py-2.5 sm:space-y-4 sm:px-4 sm:py-4">
        <GoupixDexPageHeader
          title="Mes articles"
          description="Cartes en stock, pas encore publiées sur Vinted ni eBay."
        >
          <template #actions>
            <UButton to="/articles/batch-create" color="neutral" variant="subtle" icon="i-lucide-layers">
              Création groupée
            </UButton>
            <UButton to="/articles/create" icon="i-lucide-plus"> Nouvel article </UButton>
          </template>
        </GoupixDexPageHeader>

        <GoupixDexPageTabs :items="ARTICLES_PAGE_TABS">
          <template #trailing>
            <label class="flex cursor-pointer items-center gap-2">
              <USwitch v-model="stockIncludeListed" size="sm" />
              <span class="text-muted text-xs">Inclure les articles en ligne</span>
            </label>
          </template>
        </GoupixDexPageTabs>

        <UCard v-if="!loading && !hasAnyArticles" class="ring-primary/25 ring-1" :ui="{ body: 'p-5 sm:p-6 space-y-4' }">
          <div class="space-y-2">
            <p class="text-highlighted text-sm font-medium">Aucun article pour l'instant</p>
            <p class="text-muted text-sm leading-relaxed">
              Créez une fiche ou importez votre garde-robe Vinted pour remplir votre stock.
            </p>
          </div>
          <div class="flex flex-wrap items-center gap-3">
            <UButton
              icon="i-lucide-cloud-download"
              :loading="wardrobeSyncing"
              :disabled="!isDesktopApp"
              @click="onWardrobeImportFromVinted"
            >
              Importer depuis Vinted
            </UButton>
            <UButton to="/articles/create" color="neutral" variant="subtle" icon="i-lucide-plus">
              Créer un article
            </UButton>
          </div>
          <p v-if="!isDesktopApp" class="text-muted text-xs">
            L'import Vinted n'est disponible que dans
            <NuxtLink to="/downloads" class="underline underline-offset-2">l'application desktop</NuxtLink>.
          </p>
        </UCard>

        <UCard v-else-if="!loading && stockAllListed" :ui="{ body: 'p-5 sm:p-6 space-y-4' }">
          <p class="text-highlighted text-sm font-medium">Tout votre inventaire est déjà en ligne</p>
          <p class="text-muted text-sm leading-relaxed">
            Aucune fiche « hors ligne » sur Vinted et eBay en même temps. Consultez l'onglet
            <NuxtLink to="/articles" class="text-primary font-medium underline underline-offset-2"> En ligne </NuxtLink>
            ou activez « Inclure les articles en ligne » pour tout voir ici.
          </p>
          <div class="flex flex-wrap gap-2">
            <UButton to="/articles" icon="i-lucide-store"> Voir les articles en ligne </UButton>
            <UButton color="neutral" variant="subtle" @click="stockIncludeListed = true">
              Inclure les articles en ligne
            </UButton>
          </div>
        </UCard>

        <UCard v-else :ui="{ body: 'p-0 sm:p-0' }">
          <div class="p-3 sm:p-4">
            <GoupixDexArticleList
              :articles="displayedArticles"
              :loading="loading"
              :selection-reset-key="articleListSelectionReset"
              :show-ebay-column="ebayPublishAvailable"
              :ebay-publish-available="ebayPublishAvailable"
              :vinted-channel-enabled="vintedChannelEnabled"
              :bulk-publishing="bulkPublishBusy"
              @edit="(id: number) => navigateTo(`/articles/${id}/edit`)"
              @delete="
                (id: number) => {
                  deleteId = id
                  deleteOpen = true
                }
              "
              @sold="(a) => openSold([a])"
              @bulk-sold="openSold"
              @publish-vinted="onPublishVinted"
              @publish-ebay="onPublishEbay"
              @bulk-delete="openBulkDelete"
              @bulk-publish-vinted="onBulkPublishVinted"
              @bulk-publish-ebay="onBulkPublishEbay"
              @bulk-publish-both="onBulkPublishBoth"
              @retry-cross-ebay="onRetryCrossEbay"
              @retry-cross-vinted="onRetryCrossVinted"
            />
          </div>
        </UCard>
      </div>
    </template>
  </UDashboardPanel>

  <GoupixDexArticleMarkSoldModal
    v-model:open="soldOpen"
    :articles="soldArticles"
    :ebay-enabled="ebayPublishAvailable"
    :loading="soldSubmitting"
    @confirm="confirmSold"
  />

  <UModal
    v-model:open="bulkDeleteOpen"
    title="Supprimer plusieurs articles ?"
    :description="`Vous allez supprimer ${bulkDeleteIds.length} article(s). Cette action est irréversible.`"
  >
    <template #body>
      <div class="flex justify-end gap-2">
        <UButton color="neutral" variant="subtle" @click="bulkDeleteOpen = false"> Annuler </UButton>
        <UButton color="error" @click="confirmBulkDelete"> Supprimer {{ bulkDeleteIds.length }} article(s) </UButton>
      </div>
    </template>
  </UModal>

  <UModal v-model:open="deleteOpen" title="Supprimer cet article ?" description="Cette action est irréversible.">
    <template #body>
      <div class="flex justify-end gap-2">
        <UButton color="neutral" variant="subtle" @click="deleteOpen = false"> Annuler </UButton>
        <UButton color="error" @click="confirmDelete"> Supprimer </UButton>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Mes articles — Stock',
  'Inventaire GoupixDex : cartes pas encore en ligne sur Vinted et eBay, publication et création d’annonces.',
)

const { isDesktopApp } = useDesktopRuntime()

const {
  stockIncludeListed,
  displayedArticles,
  hasAnyArticles,
  stockAllListed,
  loading,
  wardrobeSyncing,
  ebayPublishAvailable,
  vintedChannelEnabled,
  soldOpen,
  soldArticles,
  soldSubmitting,
  articleListSelectionReset,
  deleteOpen,
  deleteId,
  bulkDeleteOpen,
  bulkDeleteIds,
  bulkPublishBusy,
  confirmSold,
  confirmDelete,
  openBulkDelete,
  confirmBulkDelete,
  onWardrobeImportFromVinted,
  onPublishEbay,
  onBulkPublishVinted,
  onBulkPublishEbay,
  onBulkPublishBoth,
  onPublishVinted,
  onRetryCrossEbay,
  onRetryCrossVinted,
  openSold,
} = useArticlesListPageCore('stock')
</script>
