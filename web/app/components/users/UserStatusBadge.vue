<script setup lang="ts">
import type { UserStatus } from '~/composables/useUsers'

const props = defineProps<{
  status: UserStatus
}>()

const STATUS_META: Record<UserStatus, { label: string, color: 'success' | 'error' | 'warning' | 'neutral' }> = {
  approved: { label: 'Approuvé', color: 'success' },
  pending: { label: 'En attente', color: 'warning' },
  rejected: { label: 'Refusé', color: 'neutral' },
  banned: { label: 'Banni', color: 'error' }
}

const meta = computed(() => STATUS_META[props.status] ?? STATUS_META.pending)
</script>

<template>
  <UBadge
    :color="meta.color"
    variant="subtle"
    class="capitalize"
  >
    {{ meta.label }}
  </UBadge>
</template>
