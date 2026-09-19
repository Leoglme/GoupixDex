<template>
  <GoupixDexDialogModal
    v-model:open="open"
    :title="title"
    :description="description"
    width-class="max-w-md"
    @close="onCancel"
  >
    <template v-if="$slots.body">
      <slot name="body" />
    </template>
    <p v-else-if="body" class="text-muted text-sm leading-relaxed">{{ body }}</p>

    <template #footer>
      <button type="button" class="dialog-btn-secondary" :disabled="loading" @click="onCancel">
        {{ cancelLabel }}
      </button>
      <button
        type="button"
        :class="confirmColor === 'error' ? 'dialog-btn-danger' : 'dialog-btn-primary'"
        :disabled="loading"
        @click="onConfirm"
      >
        <UIcon v-if="loading" name="i-lucide-loader-2" class="size-4 animate-spin" />
        {{ confirmLabel }}
      </button>
    </template>
  </GoupixDexDialogModal>
</template>

<script setup lang="ts">
type ConfirmColor = 'error' | 'primary' | 'neutral' | 'warning'

withDefaults(
  defineProps<{
    title: string
    description?: string
    body?: string
    confirmLabel?: string
    cancelLabel?: string
    confirmColor?: ConfirmColor
    loading?: boolean
  }>(),
  {
    description: undefined,
    body: undefined,
    confirmLabel: 'Confirmer',
    cancelLabel: 'Annuler',
    confirmColor: 'primary',
    loading: false,
  },
)

const open = defineModel<boolean>('open', { default: false })

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

function onCancel(): void {
  open.value = false
  emit('cancel')
}

function onConfirm(): void {
  emit('confirm')
}
</script>
