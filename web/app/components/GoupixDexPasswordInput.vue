<template>
  <UInput
    v-model="model"
    :type="inputType"
    :name="props.name"
    :icon="props.icon"
    :placeholder="props.placeholder"
    :autocomplete="props.autocomplete"
    :size="props.size"
    :required="props.required"
    :disabled="props.disabled"
    class="w-full"
  >
    <template #trailing>
      <UButton
        :icon="toggleIcon"
        :aria-label="toggleLabel"
        :title="toggleLabel"
        color="neutral"
        variant="ghost"
        size="sm"
        tabindex="-1"
        @click="visible = !visible"
      />
    </template>
  </UInput>
</template>

<script setup lang="ts">
import type { ComputedRef, Ref } from 'vue'

const model = defineModel<string>({ required: true })

const props = withDefaults(
  defineProps<{
    autocomplete?: string
    placeholder?: string
    name?: string
    icon?: string
    size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl'
    required?: boolean
    disabled?: boolean
  }>(),
  {
    autocomplete: undefined,
    placeholder: undefined,
    name: undefined,
    icon: undefined,
    size: 'md',
    required: false,
    disabled: false,
  },
)

const visible: Ref<boolean> = ref(false)

const inputType: ComputedRef<'text' | 'password'> = computed(() => (visible.value ? 'text' : 'password'))
const toggleIcon: ComputedRef<string> = computed(() => (visible.value ? 'i-lucide-eye-off' : 'i-lucide-eye'))
const toggleLabel: ComputedRef<string> = computed(() =>
  visible.value ? 'Masquer le mot de passe' : 'Afficher le mot de passe',
)
</script>
