<template>
  <ul class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
    <li
      v-for="(id, i) in ids"
      :key="id"
      draggable="true"
      class="transition-opacity"
      :class="dragging === id ? 'opacity-40' : ''"
      @dragstart="onDragStart(i, id, $event)"
      @dragover.prevent
      @dragenter="moveTo(i)"
      @dragend="persist"
    >
      <NuxtLink
        :to="`/classeurs/${id}`"
        draggable="false"
        class="block overflow-hidden rounded-xl border border-(--app-line) bg-(--app-surface) p-4 transition hover:border-(--app-ink-soft) active:cursor-grabbing"
        title="Glisser pour réordonner"
      >
        <GoupixDexBinderCover
          :cover-style="tile(id).style"
          :covers="tile(id).covers"
          :name="tile(id).name"
          :color-hex="binderColorHex(tile(id).color)"
          :texture="binderDesign(tile(id).design).coverTexture"
          :layout="coverLayoutFor(id)"
        />
        <p class="mt-3 truncate text-base font-semibold group-hover:text-(--app-accent)">{{ tile(id).name }}</p>
        <p class="mt-0.5 text-sm text-(--app-ink-soft)">
          <template v-if="tile(id).pokedex_total != null">
            {{ tile(id).pokedex_owned ?? 0 }} / {{ tile(id).pokedex_total }} cartes
          </template>
          <template v-else>{{ tile(id).card_count }} carte{{ tile(id).card_count > 1 ? 's' : '' }}</template>
          <template v-if="tile(id).estimated_value_eur != null">
            · {{ formatEur(tile(id).estimated_value_eur!) }}
            <template v-if="tile(id).total_value_eur != null"> / {{ formatEur(tile(id).total_value_eur!) }}</template>
          </template>
        </p>
      </NuxtLink>
    </li>
  </ul>
</template>

<script setup lang="ts">
import type { BinderSummary } from '~/types/binders'
import type { CoverRender } from '~/utils/binder/binder-cover'
import { binderColorHex } from '~/utils/binder/binder-colors'
import { binderDesign } from '~/utils/binder/binder-design'
import { coverImageResolver, coverLayout, renderCover } from '~/utils/binder/binder-cover'
import { binderStyle } from '~/utils/binder/binder-styles'

const props = defineProps<{ binders: BinderSummary[] }>()
const emit = defineEmits<{ reordered: [] }>()

const byId = computed(() => new Map(props.binders.map((b) => [b.id, b])))
const ids = ref(props.binders.map((b) => b.id))
watch(
  () => props.binders.map((b) => b.id).join('|'),
  () => {
    ids.value = props.binders.map((b) => b.id)
  },
)

const idsRef = ref([...ids.value])
watch(ids, (v) => {
  idsRef.value = [...v]
})

const dragFrom = ref<number | null>(null)
const dragging = ref<number | null>(null)
const { reorderBinders } = useBinders()
const toast = useToast()

function tile(id: number) {
  return byId.value.get(id)!
}

/**
 * Rendu de la couverture sur mesure (poster de fond) pour la vignette de liste.
 * Renvoie null hors style `custom` : la couverture retombe alors sur son visuel par défaut.
 * @param id identifiant du classeur
 * @returns le rendu de couverture ou null
 */
function coverLayoutFor(id: number): CoverRender | null {
  const b = tile(id)
  if (binderStyle(b.style) !== 'custom') return null
  return renderCover(coverLayout(b.cover), coverImageResolver(b.cover_urls), () => null)
}

function formatEur(n: number) {
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(n)
}

function onDragStart(i: number, id: number, e: DragEvent) {
  dragFrom.value = i
  dragging.value = id
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move'
}

function moveTo(target: number) {
  const from = dragFrom.value
  if (from == null || from === target) return
  const next = [...ids.value]
  const [moved] = next.splice(from, 1)
  next.splice(target, 0, moved)
  ids.value = next
  idsRef.value = next
  dragFrom.value = target
}

async function persist() {
  dragging.value = null
  dragFrom.value = null
  try {
    await reorderBinders(idsRef.value)
    toast.add({ title: 'Ordre enregistré', color: 'success' })
    emit('reordered')
  } catch {
    toast.add({ title: 'Ordre non enregistré', color: 'error' })
  }
}
</script>
