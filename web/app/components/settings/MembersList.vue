<script setup lang="ts">
import type { AppUser } from '~/composables/useUsers'

defineProps<{
  users: AppUser[]
}>()
</script>

<template>
  <div
    v-if="users.length === 0"
    class="px-4 py-8 text-center text-sm text-muted"
  >
    Aucun utilisateur pour le moment.
  </div>
  <ul
    v-else
    role="list"
    class="divide-y divide-default"
  >
    <li
      v-for="user in users"
      :key="user.id"
      class="flex items-center justify-between gap-3 py-3 px-4 sm:px-6"
    >
      <div class="flex items-center gap-3 min-w-0">
        <UAvatar icon="i-lucide-user" size="md" />

        <div class="text-sm min-w-0">
          <p class="text-highlighted font-medium truncate">
            {{ user.email }}
          </p>
          <p class="text-muted truncate">
            {{ user.vinted_email || 'Aucun e-mail Vinted' }}
          </p>
        </div>
      </div>

      <div class="text-xs text-muted whitespace-nowrap">
        Créé le {{ new Date(user.created_at).toLocaleDateString('fr-FR') }}
      </div>
    </li>
  </ul>
</template>

