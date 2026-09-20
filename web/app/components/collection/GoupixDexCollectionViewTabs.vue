<template>
  <UTabs
    v-model="model"
    :items="items"
    size="lg"
    color="primary"
    variant="link"
    :content="content"
    aria-label="Mode d'affichage"
    :ui="{
      list: 'gap-4',
      trigger: 'px-4 py-2.5 text-base font-medium',
      leadingIcon: 'size-5',
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
