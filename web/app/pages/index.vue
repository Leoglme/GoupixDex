<script setup lang="ts">
definePageMeta({
  layout: false
})

onMounted(() => {
  const t = localStorage.getItem('goupix_token')
  navigateTo(t ? '/dashboard' : '/login', { replace: true })
})
</script>

<template>
  <div class="min-h-dvh flex items-center justify-center bg-elevated text-muted text-sm">
    Chargement…
  </div>
</template>
