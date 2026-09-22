<template>
  <UTabs
    v-model="model"
    :items="items"
    size="md"
    color="primary"
    variant="link"
    :content="content"
    aria-label="Mode d'affichage"
    :ui="{
      root: stretchMobile ? 'w-full sm:w-auto' : 'w-auto',
      list: stretchMobile ? 'w-full gap-1 p-0 sm:w-auto sm:gap-2' : 'w-auto gap-2 p-0',
      trigger: stretchMobile ? 'font-medium max-sm:flex-1 max-sm:justify-center' : 'font-medium',
      leadingIcon: 'size-4',
    }"
  />
</template>

<script setup lang="ts">
export type GoupixDexCollectionViewTabItem = {
  label: string
  value: string
  icon?: string
}

const model = defineModel<string>({ required: true })

withDefaults(
  defineProps<{
    items: GoupixDexCollectionViewTabItem[]
    /** Désactive les panneaux UTabs quand le contenu est géré en dehors (collection, classeurs). */
    content?: boolean
    /** Étire les onglets sur toute la largeur en mobile (barre d'onglets PWA). */
    stretchMobile?: boolean
  }>(),
  { content: false, stretchMobile: false },
)
</script>
