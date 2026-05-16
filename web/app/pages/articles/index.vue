<template>
  <UDashboardPanel id="articles">
    <template #header>
      <UDashboardNavbar title="Articles">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <div class="flex flex-wrap items-center gap-2">
            <UButton to="/articles/stock" color="neutral" variant="subtle" icon="i-lucide-package"> Mon stock </UButton>
            <UButton to="/articles/batch-create" color="neutral" variant="subtle" icon="i-lucide-layers">
              Création groupée
            </UButton>
            <UButton to="/articles/create" icon="i-lucide-plus"> Nouvel article </UButton>
          </div>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="w-full space-y-4 px-4 py-6 sm:space-y-6 sm:px-6 sm:py-8">
        <UCard
          v-if="!loading && !hasAnyArticles"
          class="ring-primary/25 border-primary/20 shadow-sm ring-1"
          :ui="{ body: 'p-5 sm:p-6 space-y-4' }"
        >
          <div class="space-y-2">
            <p class="text-highlighted text-sm font-medium">Aucun article pour l'instant</p>
            <p class="text-muted text-sm leading-relaxed">
              Si vous vendez déjà sur Vinted, vous pouvez importer vos annonces actives et vendues dans GoupixDex. Une
              fenêtre Chrome s'ouvre pour vous connecter ; le catalogue est ensuite récupéré automatiquement.
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
              Créer un article manuellement
            </UButton>
          </div>
          <p v-if="!isDesktopApp" class="text-muted text-xs">
            L'import Vinted n'est disponible que dans
            <NuxtLink to="/downloads" class="underline underline-offset-2">l'application desktop</NuxtLink>
            (worker local sur ce poste).
          </p>
        </UCard>

        <UCard
          v-else-if="!loading && hasAnyArticles && displayedArticles.length === 0"
          class="ring-default/60 shadow-sm ring-1"
          :ui="{ body: 'p-5 sm:p-6 space-y-4' }"
        >
          <p class="text-highlighted text-sm font-medium">Aucune annonce en ligne sur Vinted ni eBay</p>
          <p class="text-muted text-sm leading-relaxed">
            Les fiches pas encore publiées se trouvent dans
            <NuxtLink to="/articles/stock" class="text-primary font-medium underline underline-offset-2">
              Mon stock </NuxtLink
            >. Dès qu’une mise en ligne réussit, l’article apparaît ici.
          </p>
          <UButton to="/articles/stock" icon="i-lucide-package" color="neutral" variant="subtle">
            Ouvrir Mon stock
          </UButton>
        </UCard>

        <UCard v-else class="ring-default/60 shadow-sm ring-1" :ui="{ body: 'p-0 sm:p-0' }">
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
  'Articles en vente',
  'Annonces déjà en ligne sur Vinted ou eBay : suivi, mise à jour et vente dans GoupixDex.',
)

const { isDesktopApp } = useDesktopRuntime()

const {
  displayedArticles,
  hasAnyArticles,
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
} = useArticlesListPageCore('listed')
</script>
