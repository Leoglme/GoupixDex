<template>
  <div />
</template>

<script setup lang="ts">
definePageMeta({ middleware: 'auth' })

const route = useRoute()
const { openArticle } = useOpenArticleDrawer()
const { getArticle } = useArticles()

onMounted(() => {
  void (async () => {
    const id = Number(route.params.id)
    if (!Number.isFinite(id) || id <= 0) {
      await navigateTo('/articles', { replace: true })
      return
    }
    openArticle(id)
    try {
      const row = await getArticle(id)
      const listPath = row.is_sold ? '/articles/sold' : '/articles'
      if (route.path !== listPath) {
        await navigateTo(listPath, { replace: true })
      }
    } catch {
      if (route.path !== '/articles') {
        await navigateTo('/articles', { replace: true })
      }
    }
  })()
})
</script>
