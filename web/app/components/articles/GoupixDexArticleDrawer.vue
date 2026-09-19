<template>
  <Teleport to="body">
    <Transition name="goupix-drawer-backdrop">
      <div v-if="open" class="fixed inset-0 z-40 bg-(--app-overlay)" aria-hidden="true" @click="emit('close')" />
    </Transition>

    <Transition name="goupix-drawer-panel">
      <div
        v-if="open && articleId"
        class="border-default fixed top-0 right-0 z-50 flex h-dvh w-full max-w-[520px] flex-col border-l bg-(--app-surface) pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)] shadow-2xl"
        role="dialog"
        aria-modal="true"
        :aria-label="headerTitle"
      >
        <div class="border-default flex items-start gap-2 border-b px-4 py-3 sm:px-5 sm:py-4">
          <button
            v-if="showBack"
            type="button"
            class="text-muted hover:bg-elevated/60 hover:text-highlighted flex h-9 w-8 shrink-0 items-center justify-center rounded-md transition-colors"
            title="Revenir au volet précédent"
            @click="emit('back')"
          >
            <UIcon name="i-lucide-chevron-left" class="size-4" />
          </button>

          <span
            class="border-default bg-elevated/40 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border"
          >
            <UIcon name="i-lucide-layers" class="text-muted size-4" />
          </span>

          <div class="min-w-0 flex-1">
            <p v-if="headerSubtitle" class="text-muted truncate text-xs">{{ headerSubtitle }}</p>
            <h2 class="text-highlighted truncate text-base leading-tight font-semibold">
              {{ headerTitle }}
            </h2>
          </div>

          <div class="flex shrink-0 items-center gap-0.5">
            <NuxtLink
              :to="`/articles/${articleId}/edit`"
              class="text-muted hover:bg-elevated/60 hover:text-highlighted flex h-7 w-7 items-center justify-center rounded transition-colors"
              title="Modifier l'article"
              aria-label="Modifier l'article"
            >
              <UIcon name="i-lucide-square-pen" class="size-4" />
            </NuxtLink>
            <button
              type="button"
              class="text-muted hover:bg-elevated/60 hover:text-highlighted flex h-7 w-7 items-center justify-center rounded transition-colors"
              aria-label="Fermer"
              @click="emit('close')"
            >
              <UIcon name="i-lucide-x" class="size-4" />
            </button>
          </div>
        </div>

        <GoupixDexDrawerBrowseNav
          :position-label="browsePositionLabel"
          :can-previous="canBrowsePrevious"
          :can-next="canBrowseNext"
          @previous="emit('browsePrevious')"
          @next="emit('browseNext')"
        />

        <div class="min-h-0 flex-1 overflow-x-hidden overflow-y-auto px-4 py-4 sm:px-5">
          <GoupixDexArticleDetailBody
            :key="articleId"
            :article-id="articleId"
            embedded
            @updated="(a) => emit('updated', a)"
          />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import type { Article } from '~/composables/useArticles'

withDefaults(
  defineProps<{
    open: boolean
    articleId: number | null
    headerTitle?: string
    headerSubtitle?: string
    showBack?: boolean
    browsePositionLabel?: string
    canBrowsePrevious?: boolean
    canBrowseNext?: boolean
  }>(),
  {
    headerTitle: 'Article',
    headerSubtitle: '',
    showBack: false,
    browsePositionLabel: '',
    canBrowsePrevious: false,
    canBrowseNext: false,
  },
)

const emit = defineEmits<{
  close: []
  back: []
  browsePrevious: []
  browseNext: []
  updated: [article: Article]
}>()
</script>

<style scoped>
.goupix-drawer-panel-enter-active,
.goupix-drawer-panel-leave-active {
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.goupix-drawer-panel-enter-from,
.goupix-drawer-panel-leave-to {
  transform: translateX(100%);
}

.goupix-drawer-backdrop-enter-active,
.goupix-drawer-backdrop-leave-active {
  transition: opacity 0.2s ease;
}
.goupix-drawer-backdrop-enter-from,
.goupix-drawer-backdrop-leave-to {
  opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
  .goupix-drawer-panel-enter-active,
  .goupix-drawer-panel-leave-active,
  .goupix-drawer-backdrop-enter-active,
  .goupix-drawer-backdrop-leave-active {
    transition: none;
  }
}
</style>
