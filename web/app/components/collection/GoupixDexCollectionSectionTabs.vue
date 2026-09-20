<template>
  <div class="border-default flex items-center gap-1 overflow-x-auto border-b">
    <NuxtLink
      v-for="tab in tabs"
      :key="tab.value"
      :to="tab.to"
      class="-mb-px flex shrink-0 items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium transition-colors"
      :class="
        tab.value === props.active
          ? 'border-(--app-accent) text-(--app-ink)'
          : 'text-muted border-transparent hover:text-(--app-ink)'
      "
    >
      <UIcon :name="tab.icon" class="size-4" />
      {{ tab.label }}
    </NuxtLink>
  </div>
</template>

<script lang="ts" setup>
import type { PropType } from 'vue'
import type { CollectionSection, GoupixDexCollectionSectionTabsProps } from '~/types/GoupixDexCollectionSectionTabs'

interface SectionTab {
  value: CollectionSection
  label: string
  icon: string
  to: string
}

/**
 * Onglets de navigation entre les sections de la collection.
 */
const props: GoupixDexCollectionSectionTabsProps = defineProps({
  active: {
    type: String as PropType<CollectionSection>,
    required: true,
  },
})

const tabs: SectionTab[] = [
  { value: 'cartes', label: 'Cartes', icon: 'i-lucide-layers', to: '/collection' },
  { value: 'produits', label: 'Produits scellés', icon: 'i-lucide-box', to: '/collection/produits' },
  { value: 'valeur', label: 'Valeur', icon: 'i-lucide-line-chart', to: '/collection/valeur' },
]
</script>
