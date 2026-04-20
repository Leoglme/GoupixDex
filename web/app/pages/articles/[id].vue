<script setup lang="ts">
import type { Article, ArticleUpdateBody } from '~/composables/useArticles'

definePageMeta({ middleware: 'auth' })

const route = useRoute()
const id = computed(() => Number(route.params.id))

const { getArticle, updateArticle, publishArticleToEbay } = useArticles()
const toast = useToast()

const article = ref<Article | null>(null)
const loading = ref(true)
const submitting = ref(false)
const publishingEbay = ref(false)

async function load() {
  loading.value = true
  try {
    article.value = await getArticle(id.value)
  } catch (e) {
    toast.add({ title: 'Article introuvable', description: apiErrorMessage(e), color: 'error' })
    await navigateTo('/articles')
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function publishEbay() {
  publishingEbay.value = true
  try {
    const { ebay } = await publishArticleToEbay(id.value)
    if (ebay?.status === 'running' && ebay?.stream_path) {
      await navigateTo({
        path: '/articles/listing-logs',
        query: { article: String(id.value) }
      })
      return
    }
    toast.add({
      title: 'Publication eBay démarrée',
      description: 'Traitement en arrière-plan — rafraîchissez la liste dans quelques instants.',
      color: 'success'
    })
    await load()
  } catch (e) {
    toast.add({ title: 'eBay', description: apiErrorMessage(e), color: 'error' })
  } finally {
    publishingEbay.value = false
  }
}

async function onSubmitEdit(body: ArticleUpdateBody) {
  submitting.value = true
  try {
    await updateArticle(id.value, body)
    toast.add({ title: 'Article mis à jour', color: 'success' })
    await navigateTo('/articles')
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  } finally {
    submitting.value = false
  }
}

function articleTitleForSeo(a: Article) {
  const t = a.title
  return t.length > 42 ? `${t.slice(0, 39)}…` : t
}

useSeoMeta({
  title: computed(() => {
    if (!article.value) {
      return 'Article · GoupixDex'
    }
    return `${articleTitleForSeo(article.value)} — modification · GoupixDex`
  }),
  ogTitle: computed(() => {
    if (!article.value) {
      return 'Article · GoupixDex'
    }
    return `${articleTitleForSeo(article.value)} — modification · GoupixDex`
  }),
  description: computed(() => {
    if (!article.value) {
      return 'Modifiez une fiche carte ou annonce dans GoupixDex.'
    }
    return `Éditez « ${article.value.title} » dans GoupixDex : prix, état, photos, description et statut Vinted.`
  }),
  ogDescription: computed(() => {
    if (!article.value) {
      return 'Modifiez une fiche carte ou annonce dans GoupixDex.'
    }
    return `Éditez « ${article.value.title} » dans GoupixDex : prix, état, photos, description et statut Vinted.`
  })
})
</script>

<template>
  <UDashboardPanel :id="`article-${id}`">
    <template #header>
      <UDashboardNavbar title="Modifier l'article">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton to="/articles" color="neutral" variant="ghost">
            Retour
          </UButton>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="p-4 sm:p-6 max-w-3xl">
        <div v-if="loading" class="flex justify-center py-16">
          <UIcon name="i-lucide-loader-2" class="size-8 animate-spin text-primary" />
        </div>
        <div v-else-if="article" class="space-y-4">
          <div class="flex flex-wrap items-center gap-2">
            <span class="text-sm text-muted">Publication Vinted</span>
            <UBadge
              :color="(article.published_on_vinted ?? false) ? 'success' : 'neutral'"
              variant="subtle"
            >
              {{ (article.published_on_vinted ?? false) ? 'Oui' : 'Non' }}
            </UBadge>
            <span class="text-sm text-muted">eBay</span>
            <UBadge
              :color="(article.published_on_ebay ?? false) ? 'success' : 'neutral'"
              variant="subtle"
            >
              {{ (article.published_on_ebay ?? false) ? 'Oui' : 'Non' }}
            </UBadge>
            <UButton
              v-if="!article.is_sold && !(article.published_on_ebay ?? false)"
              size="xs"
              variant="soft"
              color="primary"
              :loading="publishingEbay"
              icon="i-lucide-shopping-bag"
              @click="publishEbay"
            >
              Publier sur eBay
            </UButton>
          </div>
          <ArticleForm
            mode="edit"
            :article="article"
            :loading="submitting"
            @submit-edit="onSubmitEdit"
          />
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>
