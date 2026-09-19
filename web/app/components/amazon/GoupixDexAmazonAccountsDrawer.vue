<template>
  <GoupixDexAppDrawer
    :open="open"
    title="Comptes Amazon"
    subtitle="Coffre chiffré · profil Chrome par compte"
    icon="i-simple-icons-amazon"
    @close="open = false"
  >
    <GoupixDexAmazonAccountsVault ref="vaultRef" @changed="emit('changed')" />
  </GoupixDexAppDrawer>
</template>

<script setup lang="ts">
import type { Ref } from 'vue'

const open = defineModel<boolean>('open', { default: false })

const emit = defineEmits<{
  changed: []
}>()

const vaultRef: Ref<{ reload: () => Promise<void>; openCreate: () => void } | null> = ref(null)

watch(
  open,
  (isOpen) => {
    if (isOpen) {
      void nextTick(() => vaultRef.value?.reload())
    }
  },
  { flush: 'post' },
)

function openCreateAccount(): void {
  open.value = true
  void nextTick(() => vaultRef.value?.openCreate())
}

defineExpose({ openCreateAccount })
</script>
