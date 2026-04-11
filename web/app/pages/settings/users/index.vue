<script setup lang="ts">
definePageMeta({ middleware: 'auth' })

const { listUsers } = useUsers()
const toast = useToast()

const users = ref<Awaited<ReturnType<typeof listUsers>>>([])
const q = ref('')
const loading = ref(true)

async function loadUsers() {
  loading.value = true
  try {
    users.value = await listUsers()
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  } finally {
    loading.value = false
  }
}

onMounted(loadUsers)

const filteredUsers = computed(() => {
  const query = q.value.trim().toLowerCase()
  if (!query) {
    return users.value
  }
  return users.value.filter((user) => {
    return user.email.toLowerCase().includes(query) || (user.vinted_email ?? '').toLowerCase().includes(query)
  })
})
</script>

<template>
  <div>
    <UPageCard
      title="Utilisateurs"
      description="Gérez les utilisateurs de l'application."
      variant="naked"
      orientation="horizontal"
      class="mb-4"
    >
      <UButton
        label="Créer un utilisateur"
        color="primary"
        variant="solid"
        class="w-fit lg:ms-auto"
        to="/settings/users/create"
      />
    </UPageCard>

    <UPageCard variant="subtle" :ui="{ container: 'p-0 sm:p-0 gap-y-0', wrapper: 'items-stretch', header: 'p-4 mb-0 border-b border-default' }">
      <template #header>
        <UInput
          v-model="q"
          icon="i-lucide-search"
          placeholder="Rechercher un utilisateur"
          autofocus
          class="w-full"
        />
      </template>
      <div v-if="loading" class="p-4 text-sm text-muted">
        Chargement des utilisateurs...
      </div>
      <MembersList v-else :users="filteredUsers" />
    </UPageCard>
  </div>
</template>
