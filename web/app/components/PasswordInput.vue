<script setup lang="ts">
const model = defineModel<string>({ required: true })

const props = withDefaults(defineProps<{
  autocomplete?: string
  placeholder?: string
  name?: string
  icon?: string
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl'
  required?: boolean
  disabled?: boolean
}>(), {
  autocomplete: undefined,
  placeholder: undefined,
  name: undefined,
  icon: undefined,
  size: 'md',
  required: false,
  disabled: false
})

const visible = ref(false)

const inputType = computed(() => visible.value ? 'text' : 'password')
const toggleIcon = computed(() => visible.value ? 'i-lucide-eye-off' : 'i-lucide-eye')
const toggleLabel = computed(() => visible.value ? 'Masquer le mot de passe' : 'Afficher le mot de passe')
</script>

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
