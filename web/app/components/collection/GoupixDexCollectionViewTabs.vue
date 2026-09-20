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
      root: 'w-auto',
      list: 'w-auto gap-2 p-0',
      trigger: 'font-medium',
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
  }>(),
  { content: false },
)
</script>
