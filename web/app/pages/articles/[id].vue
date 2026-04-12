<script setup lang="ts">
import type { Article, ArticleUpdateBody } from '~/composables/useArticles'

definePageMeta({ middleware: 'auth' })

const route = useRoute()
const id = computed(() => Number(route.params.id))

const { getArticle, updateArticle } = useArticles()
const toast = useToast()

const article = ref<Article | null>(null)
const loading = ref(true)
const submitting = ref(false)

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
