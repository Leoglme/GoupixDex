<template>
  <Teleport to="body">
    <Transition name="goupix-catalog-drawer-backdrop">
      <div v-if="open" class="fixed inset-0 z-40 bg-(--app-overlay)" aria-hidden="true" @click="emit('close')" />
    </Transition>

    <Transition name="goupix-catalog-drawer-panel">
      <div
        v-if="open && product"
        class="border-default fixed top-0 right-0 z-50 flex h-dvh w-full max-w-[520px] flex-col border-l bg-(--app-surface) pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)] shadow-2xl"
        role="dialog"
        aria-modal="true"
        :aria-label="product.n"
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
            <UIcon name="i-lucide-box" class="text-muted size-4" />
          </span>

          <div class="min-w-0 flex-1">
            <p class="text-muted truncate text-xs">{{ expansionName }}</p>
            <h2 class="text-highlighted truncate text-base leading-tight font-semibold">{{ product.n }}</h2>
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
          <GoupixDexSealedCatalogPreviewBody
            :key="product.tp"
            :product="product"
            :expansion-name="expansionName"
            @added="(p) => emit('added', p)"
          />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import type { PropType } from 'vue'
import type { SealedProduct } from '~/composables/useSealed'
import type { SealedCatalogProduct } from '~/composables/useSealedCatalog'

defineProps({
  open: {
    type: Boolean,
    default: false,
  },
  product: {
    type: Object as PropType<SealedCatalogProduct | null>,
    default: null,
  },
  expansionName: {
    type: String,
    default: '',
  },
  showBack: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits<{
  close: []
  back: []
  added: [product: SealedProduct]
}>()
</script>

<style scoped>
.goupix-catalog-drawer-panel-enter-active,
.goupix-catalog-drawer-panel-leave-active {
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.goupix-catalog-drawer-panel-enter-from,
.goupix-catalog-drawer-panel-leave-to {
  transform: translateX(100%);
}

.goupix-catalog-drawer-backdrop-enter-active,
.goupix-catalog-drawer-backdrop-leave-active {
  transition: opacity 0.2s ease;
}
.goupix-catalog-drawer-backdrop-enter-from,
.goupix-catalog-drawer-backdrop-leave-to {
  opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
  .goupix-catalog-drawer-panel-enter-active,
  .goupix-catalog-drawer-panel-leave-active,
  .goupix-catalog-drawer-backdrop-enter-active,
  .goupix-catalog-drawer-backdrop-leave-active {
    transition: none;
  }
}
</style>
