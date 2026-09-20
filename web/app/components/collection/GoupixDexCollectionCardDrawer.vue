<template>
  <Teleport to="body">
    <Transition name="goupix-card-drawer-backdrop">
      <div v-if="open" class="fixed inset-0 z-40 bg-(--app-overlay)" aria-hidden="true" @click="emit('close')" />
    </Transition>

    <Transition name="goupix-card-drawer-panel">
      <div
        v-if="open && cardId"
        class="border-default fixed top-0 right-0 z-50 flex h-dvh w-full max-w-[520px] flex-col border-l bg-(--app-surface) pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)] shadow-2xl"
        role="dialog"
        aria-modal="true"
        :aria-label="headerTitle"
      >
        <div class="border-default flex items-start gap-2 border-b px-4 py-3 sm:px-5 sm:py-4">
          <button
            v-if="showBack"
            type="button"
            class="text-muted hover:bg-elevated/60 hover:text-highlighted focus-visible:ring-primary flex h-9 w-8 shrink-0 items-center justify-center rounded-md transition-colors focus-visible:ring-2 focus-visible:outline-none"
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
            <h2 class="text-highlighted truncate text-base leading-tight font-semibold">{{ headerTitle }}</h2>
          </div>

          <button
            type="button"
            class="text-muted hover:bg-elevated/60 hover:text-highlighted focus-visible:ring-primary flex h-7 w-7 shrink-0 items-center justify-center rounded transition-colors focus-visible:ring-2 focus-visible:outline-none"
            aria-label="Fermer"
            @click="emit('close')"
          >
            <UIcon name="i-lucide-x" class="size-4" />
          </button>
        </div>

        <div class="min-h-0 flex-1 overflow-x-hidden overflow-y-auto px-4 py-4 sm:px-5">
          <GoupixDexCollectionCardDetailBody
            :key="cardId"
            :card-id="cardId"
            @updated="(c) => emit('updated', c)"
            @deleted="(id) => emit('deleted', id)"
          />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import type { CollectionCard } from '~/composables/useCollection'

withDefaults(
  defineProps<{
    open: boolean
    cardId: number | null
    headerTitle?: string
    headerSubtitle?: string
    showBack?: boolean
  }>(),
  {
    headerTitle: 'Carte de collection',
    headerSubtitle: '',
    showBack: false,
  },
)

const emit = defineEmits<{
  close: []
  back: []
  updated: [card: CollectionCard]
  deleted: [cardId: number]
}>()
</script>

<style scoped>
.goupix-card-drawer-panel-enter-active,
.goupix-card-drawer-panel-leave-active {
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.goupix-card-drawer-panel-enter-from,
.goupix-card-drawer-panel-leave-to {
  transform: translateX(100%);
}

.goupix-card-drawer-backdrop-enter-active,
.goupix-card-drawer-backdrop-leave-active {
  transition: opacity 0.2s ease;
}
.goupix-card-drawer-backdrop-enter-from,
.goupix-card-drawer-backdrop-leave-to {
  opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
  .goupix-card-drawer-panel-enter-active,
  .goupix-card-drawer-panel-leave-active,
  .goupix-card-drawer-backdrop-enter-active,
  .goupix-card-drawer-backdrop-leave-active {
    transition: none;
  }
}
</style>
