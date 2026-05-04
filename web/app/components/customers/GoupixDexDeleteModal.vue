<template>
  <UModal
    v-model:open="open"
    :title="`Delete ${count} customer${count > 1 ? 's' : ''}`"
    :description="`Are you sure, this action cannot be undone.`"
  >
    <slot />

    <template #body>
      <div class="flex justify-end gap-2">
        <UButton label="Cancel" color="neutral" variant="subtle" @click="open = false" />
        <UButton label="Delete" color="error" variant="solid" loading-auto @click="onSubmit" />
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import type { Ref } from 'vue'

withDefaults(
  defineProps<{
    count?: number
  }>(),
  {
    count: 0,
  },
)

const open: Ref<boolean> = ref(false)

async function onSubmit() {
  await new Promise((resolve) => setTimeout(resolve, 1000))
  open.value = false
}
</script>
