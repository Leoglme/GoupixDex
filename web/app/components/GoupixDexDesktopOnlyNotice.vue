<template>
  <div class="app-card flex flex-col items-center gap-4 px-6 py-12 text-center">
    <span class="app-icon-tile !h-12 !w-12">
      <UIcon name="i-lucide-monitor-down" class="h-6 w-6 text-(--app-accent)" />
    </span>
    <div class="space-y-1.5">
      <h2 class="text-highlighted text-lg font-semibold">{{ props.featureLabel }} — disponible sur l'app desktop</h2>
      <p class="text-muted mx-auto max-w-md text-sm leading-relaxed">
        {{
          props.reason ??
          'Cette fonctionnalité pilote un navigateur local sur votre poste et ne peut pas tourner dans la version web.'
        }}
      </p>
    </div>
    <UButton to="/downloads" icon="i-lucide-hard-drive-download"> Télécharger l'application </UButton>
  </div>
</template>

<script lang="ts" setup>
import type { GoupixDexDesktopOnlyNoticeProps } from '~/types/GoupixDexDesktopOnlyNotice'

/**
 * Define the GoupixDexDesktopOnlyNotice props.
 */
const props: GoupixDexDesktopOnlyNoticeProps = defineProps({
  featureLabel: {
    type: String,
    required: true,
  },
  reason: {
    type: String,
    default: undefined,
  },
})
</script>
