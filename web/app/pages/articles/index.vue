<template>
  <UDashboardPanel id="articles">
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
          description="Cartes de votre collection mises en vente — publiées ou en préparation."
        >
          <template #actions>
            <UButton to="/articles/batch-create" color="neutral" variant="subtle" icon="i-lucide-layers">
              Création groupée
            </UButton>
            <UButton to="/articles/create" icon="i-lucide-plus"> Nouvel article </UButton>
          </template>
        </GoupixDexPageHeader>

        <GoupixDexPageTabs :items="ARTICLES_PAGE_TABS" />
        <div v-if="!loading && !hasAnyArticles" class="app-card ring-primary/25 space-y-4 p-5 ring-1 sm:p-6">
          <div class="space-y-2">
            <p class="text-sm font-medium text-[var(--app-ink)]">Aucun article pour l'instant</p>
            <p class="text-sm leading-relaxed text-[var(--app-ink-soft)]">
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
          <p v-if="!isDesktopApp" class="text-xs text-[var(--app-ink-soft)]">
            L'import Vinted n'est disponible que dans
            <NuxtLink to="/downloads" class="underline underline-offset-2">l'application desktop</NuxtLink>
            (worker local sur ce poste).
          </p>
        </div>

        <div
          v-else-if="!loading && hasAnyArticles && displayedArticles.length === 0"
          class="app-card space-y-4 p-5 sm:p-6"
        >
          <p class="text-sm font-medium text-[var(--app-ink)]">Aucun article en cours de vente</p>
          <p class="text-sm leading-relaxed text-[var(--app-ink-soft)]">
            Tous vos articles sont marqués vendus. Consultez l’onglet
            <NuxtLink to="/articles/sold" class="text-primary font-medium underline underline-offset-2">
              Vendus
            </NuxtLink>
            ou créez une fiche depuis
            <NuxtLink to="/collection" class="text-primary font-medium underline underline-offset-2">
              Ma collection </NuxtLink
            >.
          </p>
        </div>

        <GoupixDexArticleList
          v-else
          variant="listed"
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
  'Mes articles — En ligne',
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
