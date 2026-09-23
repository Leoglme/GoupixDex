<template>
  <UTabs
    v-model="model"
    :items="items"
    size="md"
    color="primary"
    variant="link"
    :content="content"
    aria-label="Mode d'affichage"
    :ui="tabsUi"
  />
</template>

<script setup lang="ts">
import type { ComputedRef, PropType } from 'vue'

export type GoupixDexCollectionViewTabItem = {
  label: string
  value: string
  icon?: string
}

type GoupixDexCollectionViewTabsUi = {
  root: string
  list: string
  trigger: string
  leadingIcon: string
}

const model = defineModel<string>({ required: true })

/**
 * Barre d'onglets de bascule de vue (ventes/collection, pages/grille…), avec modes d'étirement.
 */
const props = defineProps({
  items: {
    type: Array as PropType<GoupixDexCollectionViewTabItem[]>,
    required: true,
  },
  /** Désactive les panneaux UTabs quand le contenu est géré en dehors (collection, classeurs). */
  content: {
    type: Boolean,
    default: false,
  },
  /** Étire les onglets sur toute la largeur en mobile uniquement (barre d'onglets PWA, compacte sur desktop). */
  stretchMobile: {
    type: Boolean,
    default: false,
  },
  /** Étire les onglets sur toute la largeur à toutes les tailles d'écran (barre pleine largeur). */
  stretch: {
    type: Boolean,
    default: false,
  },
})

/**
 * Classes UTabs selon le mode d'étirement demandé (pleine largeur, pleine largeur mobile, ou compact).
 * @returns Le mapping de classes passé au slot `ui` de UTabs.
 */
const tabsUi: ComputedRef<GoupixDexCollectionViewTabsUi> = computed(() => {
  if (props.stretch) {
    return {
      root: 'w-full',
      list: 'w-full gap-1 p-0',
      trigger: 'font-medium flex-1 justify-center',
      leadingIcon: 'size-4',
    }
  }
  if (props.stretchMobile) {
    return {
      root: 'w-full sm:w-auto',
      list: 'w-full gap-1 p-0 sm:w-auto sm:gap-2',
      trigger: 'font-medium max-sm:flex-1 max-sm:justify-center',
      leadingIcon: 'size-4',
    }
  }
  return {
    root: 'w-auto',
    list: 'w-auto gap-2 p-0',
    trigger: 'font-medium',
    leadingIcon: 'size-4',
  }
})
</script>
