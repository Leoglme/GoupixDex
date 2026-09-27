<template>
  <GoupixDexDialogModal
    v-model:open="promptState.isOpen"
    title="Modifier avant de publier ?"
    :description="promptDescription"
    width-class="max-w-md"
    @close="answerPublishReviewPrompt(null)"
  >
    <p class="text-muted text-sm leading-relaxed">
      Ajustez le prix avec les repères Cardmarket ou complétez la fiche avant la mise en ligne.
    </p>

    <template #footer>
      <button type="button" class="dialog-btn-secondary" @click="answerPublishReviewPrompt('publish')">
        Non, publier
      </button>
      <button type="button" class="dialog-btn-primary" @click="answerPublishReviewPrompt('review')">
        Oui, modifier
      </button>
    </template>
  </GoupixDexDialogModal>
</template>

<script lang="ts" setup>
import type { ComputedRef } from 'vue'
import type { PublishReviewPrompt, PublishReviewRequest } from '~/types/PublishReviewPrompt'
import { usePublishReviewPrompt } from '~/composables/usePublishReviewPrompt'
import { marketplaceNamesLabel } from '~/utils/marketplaces'

const { promptState, answerPublishReviewPrompt }: PublishReviewPrompt = usePublishReviewPrompt()

const promptDescription: ComputedRef<string> = computed((): string => {
  const request: PublishReviewRequest | null = promptState.value.request
  return request ? `${request.subjectLabel} · ${marketplaceNamesLabel(request.marketplaces)}` : ''
})
</script>
