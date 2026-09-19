<template>
  <Teleport to="body">
    <Transition name="lightbox">
      <div
        v-if="isOpen"
        class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/90 p-4 backdrop-blur-sm"
        role="dialog"
        aria-modal="true"
        aria-label="Image en plein écran"
        @click="close"
      >
        <button
          type="button"
          class="absolute top-4 right-4 z-10 flex h-11 w-11 cursor-pointer items-center justify-center rounded-full bg-white/10 text-white transition-all duration-300 hover:rotate-90 hover:bg-white/20"
          aria-label="Fermer"
          @click.stop="close"
        >
          <UIcon name="i-lucide-x" class="h-6 w-6" />
        </button>

        <button
          v-if="hasMultiple"
          type="button"
          class="absolute left-3 z-10 flex h-11 w-11 cursor-pointer items-center justify-center rounded-full bg-white/10 text-white transition-colors duration-200 hover:bg-white/20 sm:left-6"
          aria-label="Image précédente"
          @click.stop="prev"
        >
          <UIcon name="i-lucide-chevron-left" class="h-6 w-6" />
        </button>

        <div class="relative flex max-h-[90vh] max-w-[92vw] items-center justify-center" @click.stop>
          <img
            :key="currentPhoto"
            :src="currentPhoto"
            :alt="`Image ${currentIndex + 1} sur ${photos.length}`"
            class="lightbox__img h-auto max-h-[90vh] w-auto max-w-[92vw] rounded-xl object-contain"
          />
        </div>

        <button
          v-if="hasMultiple"
          type="button"
          class="absolute right-3 z-10 flex h-11 w-11 cursor-pointer items-center justify-center rounded-full bg-white/10 text-white transition-colors duration-200 hover:bg-white/20 sm:right-6"
          aria-label="Image suivante"
          @click.stop="next"
        >
          <UIcon name="i-lucide-chevron-right" class="h-6 w-6" />
        </button>

        <div
          v-if="hasMultiple"
          class="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full bg-white/10 px-3 py-1 text-sm font-medium text-white tabular-nums"
        >
          {{ currentIndex + 1 }} / {{ photos.length }}
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import type { ComputedRef } from 'vue'

const props = defineProps<{
  photos: string[]
}>()

const openIndex = defineModel<number | null>({ default: null })

const isOpen: ComputedRef<boolean> = computed(
  (): boolean => openIndex.value !== null && openIndex.value >= 0 && openIndex.value < props.photos.length,
)
const currentIndex: ComputedRef<number> = computed((): number => openIndex.value ?? 0)
const currentPhoto: ComputedRef<string> = computed((): string => props.photos[currentIndex.value] ?? '')
const hasMultiple: ComputedRef<boolean> = computed((): boolean => props.photos.length > 1)

function close(): void {
  openIndex.value = null
}

function prev(): void {
  if (!props.photos.length) return
  openIndex.value = (currentIndex.value - 1 + props.photos.length) % props.photos.length
}

function next(): void {
  if (!props.photos.length) return
  openIndex.value = (currentIndex.value + 1) % props.photos.length
}

function onKeydown(event: KeyboardEvent): void {
  if (!isOpen.value) return
  if (event.key === 'Escape') {
    close()
  } else if (event.key === 'ArrowLeft') {
    prev()
  } else if (event.key === 'ArrowRight') {
    next()
  }
}

watch(isOpen, (open: boolean): void => {
  if (!import.meta.client) return
  document.body.style.overflow = open ? 'hidden' : ''
  if (open) {
    window.addEventListener('keydown', onKeydown)
  } else {
    window.removeEventListener('keydown', onKeydown)
  }
})

onBeforeUnmount((): void => {
  if (!import.meta.client) return
  document.body.style.overflow = ''
  window.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped>
.lightbox-enter-active,
.lightbox-leave-active {
  transition: opacity 0.25s ease;
}

.lightbox-enter-from,
.lightbox-leave-to {
  opacity: 0;
}

.lightbox-enter-active .lightbox__img,
.lightbox-leave-active .lightbox__img {
  transition: transform 0.25s ease;
}

.lightbox-enter-from .lightbox__img,
.lightbox-leave-to .lightbox__img {
  transform: scale(0.92);
}
</style>
