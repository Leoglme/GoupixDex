<script setup lang="ts">
const model = defineModel<string>({ required: true })

const props = withDefaults(defineProps<{
  title?: string
  subtitle?: string
  previewUrl?: string | null
  scanning?: boolean
  inputKey?: number
  hintDisabled?: boolean
  hintLabel?: string
  hintDescription?: string
  hintPlaceholder?: string
}>(), {
  title: 'Scanner une carte',
  subtitle: 'Scan de carte + prix PokéWallet (Cardmarket / TCGPlayer) pour préremplir le formulaire.',
  previewUrl: null,
  scanning: false,
  inputKey: 0,
  hintDisabled: false,
  hintLabel: 'Indice pour le scan (optionnel)',
  hintDescription: 'Si la photo est floue ou difficile, indiquez par ex. le Pokemon, l\'extension, le code set (SV5a...) ou le n de carte pour aider la reconnaissance.',
  hintPlaceholder: 'Ex. Pikachu SV5a 063/065, ou Gloupti M1L...'
})

const emit = defineEmits<{
  choose: []
  fileSelected: [file: File]
  hintBlur: []
}>()

const fileInput = ref<HTMLInputElement | null>(null)

function triggerChoose() {
  emit('choose')
  fileInput.value?.click()
}

function onInputChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  emit('fileSelected', file)
}
</script>

<template>
  <UCard class="ring-1 ring-default/60 shadow-sm">
    <template #header>
      <div>
        <p class="font-medium text-highlighted">
          {{ props.title }}
        </p>
        <p class="text-sm text-muted">
          {{ props.subtitle }}
        </p>
      </div>
    </template>
    <div class="space-y-4">
      <div class="flex items-center gap-3">
        <div
          v-if="props.previewUrl"
          class="w-24 h-24 rounded-lg overflow-hidden bg-elevated ring ring-default shrink-0"
        >
          <img :src="props.previewUrl" alt="Previsualisation carte" class="w-full h-full object-cover">
        </div>
        <div class="flex-1 space-y-2">
          <UButton
            size="sm"
            color="primary"
            variant="outline"
            icon="i-lucide-image-up"
            :disabled="props.scanning"
            @click="triggerChoose"
          >
            {{ props.previewUrl ? 'Changer la photo' : 'Choisir une photo' }}
          </UButton>
          <p class="text-xs text-muted">
            JPEG, PNG ou WebP. Utilisez une photo nette de la carte entiere.
          </p>
        </div>
      </div>
      <input
        :key="props.inputKey"
        ref="fileInput"
        type="file"
        accept="image/*"
        class="hidden"
        @change="onInputChange"
      >
      <UIcon
        v-if="props.scanning"
        name="i-lucide-loader-2"
        class="size-5 animate-spin text-primary"
      />
      <UFormField
        :label="props.hintLabel"
        :description="props.hintDescription"
        class="w-full"
      >
        <UInput
          v-model="model"
          :placeholder="props.hintPlaceholder"
          :disabled="props.hintDisabled || props.scanning"
          class="mt-3 w-full sm:mt-4"
          @blur="emit('hintBlur')"
        />
      </UFormField>
    </div>
  </UCard>
</template>
