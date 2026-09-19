<template>
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div class="flex items-center gap-2">
      <UBadge :color="badge.color" variant="subtle">{{ badge.label }}</UBadge>
      <p v-if="session?.message" class="text-muted text-xs">{{ session.message }}</p>
    </div>
    <div class="flex flex-wrap gap-2">
      <UButton
        size="sm"
        color="neutral"
        variant="ghost"
        icon="i-lucide-refresh-cw"
        :loading="sessionLoading"
        @click="emit('refresh')"
      >
        État session
      </UButton>
      <UButton size="sm" color="neutral" variant="soft" icon="i-lucide-chrome" @click="emit('open-chrome')">
        Chrome manuel
      </UButton>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AmazonSessionResponse } from '~/types/amazonInvites'
import { amazonSessionBadge } from '~/utils/amazonConnectionUi'

const props = defineProps<{
  session: AmazonSessionResponse | null
  sessionLoading?: boolean
}>()

const emit = defineEmits<{
  refresh: []
  'open-chrome': []
}>()

const badge = computed(() => amazonSessionBadge(props.session))
</script>
