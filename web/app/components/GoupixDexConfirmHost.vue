<template>
  <GoupixDexConfirmModal
    v-if="state.options"
    v-model:open="state.open"
    :title="state.options.title"
    :description="state.options.description"
    :body="state.options.body"
    :confirm-label="state.options.confirmLabel ?? 'Confirmer'"
    :cancel-label="state.options.cancelLabel ?? 'Annuler'"
    :confirm-color="state.options.confirmColor ?? 'primary'"
    @confirm="finish(true)"
    @cancel="finish(false)"
  />
</template>

<script setup lang="ts">
const { state, finish } = useGoupixConfirm()
</script>
