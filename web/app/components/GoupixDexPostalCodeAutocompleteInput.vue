<template>
  <div ref="rootRef" class="relative w-full">
    <UInput
      :id="inputId"
      :model-value="modelValue"
      :placeholder="placeholder"
      :required="required"
      :disabled="disabled"
      inputmode="numeric"
      autocomplete="postal-code"
      role="combobox"
      :aria-expanded="isOpen"
      class="w-full"
      maxlength="5"
      @update:model-value="onModelUpdate"
      @focus="handleFocus"
      @blur="handleBlur"
      @keydown="handleKeydown"
    />

    <component :is="teleportToBody ? Teleport : 'div'" :to="teleportToBody ? 'body' : undefined">
      <ul
        v-if="isOpen && (!teleportToBody || menuStyle)"
        class="border-default bg-default max-h-56 overflow-auto rounded-md border shadow-lg"
        :class="teleportToBody ? 'fixed z-[55]' : 'absolute z-20 mt-1 w-full'"
        :style="teleportToBody ? (menuStyle ?? undefined) : undefined"
      >
        <li v-if="isSearching" class="text-muted flex items-center gap-2 px-3 py-2 text-sm">
          <UIcon name="i-lucide-loader-circle" class="size-3.5 animate-spin" />
          Recherche…
        </li>
        <li v-else-if="suggestions.length === 0" class="text-muted px-3 py-2 text-sm">
          Aucune ville pour ce code postal
        </li>
        <template v-else>
          <li
            v-for="(suggestion, index) in suggestions"
            :key="`${modelValue}-${suggestion.nom}`"
            class="flex cursor-pointer items-center gap-3 px-3 py-2 text-sm"
            :class="index === activeIndex ? 'bg-elevated' : 'hover:bg-elevated/80'"
            @mousedown.prevent="selectSuggestion(suggestion)"
            @mousemove="activeIndex = index"
          >
            <span class="text-highlighted min-w-0 flex-1 font-medium">{{ suggestion.nom }}</span>
            <span class="text-muted shrink-0 text-xs tabular-nums">{{ modelValue }}</span>
          </li>
        </template>
      </ul>
    </component>
  </div>
</template>

<script setup lang="ts">
import type { CSSProperties, Ref } from 'vue'
import { Teleport } from 'vue'
import { useDebounceFn, useEventListener } from '@vueuse/core'
import type { PostalCodeAutocompleteInputProps, PostalCodeCitySuggestion } from '~/types/PostalCodeAutocompleteInput'
import { POSTAL_CODE_LOOKUP_LENGTH, searchCitiesByPostalCode } from '~/services/franceGeoAutocompleteService'

const debounceDelayMs = 300
const blurCloseDelayMs = 150

const props = withDefaults(defineProps<PostalCodeAutocompleteInputProps>(), {
  placeholder: '35000',
  inputId: undefined,
  required: false,
  disabled: false,
  teleportToBody: true,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  select: [suggestion: PostalCodeCitySuggestion]
}>()

const rootRef = ref<HTMLElement | null>(null)
const menuStyle: Ref<CSSProperties | null> = ref(null)
const suggestions: Ref<PostalCodeCitySuggestion[]> = ref([])
const isSearching: Ref<boolean> = ref(false)
const isOpen: Ref<boolean> = ref(false)
const activeIndex: Ref<number> = ref(-1)
let searchRequestId = 0
let blurTimeoutId: ReturnType<typeof setTimeout> | null = null

function syncMenuPosition(): void {
  if (!props.teleportToBody) {
    return
  }
  const el = rootRef.value
  if (!el) {
    menuStyle.value = null
    return
  }
  const rect = el.getBoundingClientRect()
  menuStyle.value = {
    top: `${rect.bottom + 4}px`,
    left: `${rect.left}px`,
    width: `${rect.width}px`,
  }
}

useEventListener(window, 'scroll', syncMenuPosition, true)
useEventListener(window, 'resize', syncMenuPosition)

const fetchSuggestions = useDebounceFn(async (postalCode: string): Promise<void> => {
  const trimmedCode = postalCode.trim()
  if (trimmedCode.length < POSTAL_CODE_LOOKUP_LENGTH) {
    suggestions.value = []
    isOpen.value = false
    menuStyle.value = null
    return
  }

  const requestId = ++searchRequestId
  isSearching.value = true
  isOpen.value = true
  syncMenuPosition()

  try {
    const results = await searchCitiesByPostalCode(trimmedCode)
    if (requestId !== searchRequestId) {
      return
    }
    suggestions.value = results
    syncMenuPosition()
    if (results.length === 1) {
      selectSuggestion(results[0] as PostalCodeCitySuggestion)
    }
  } catch {
    if (requestId !== searchRequestId) {
      return
    }
    suggestions.value = []
  } finally {
    if (requestId === searchRequestId) {
      isSearching.value = false
      activeIndex.value = -1
    }
  }
}, debounceDelayMs)

function onModelUpdate(raw: string) {
  if (props.disabled) {
    return
  }
  const digitsOnly = raw.replace(/\D/g, '').slice(0, POSTAL_CODE_LOOKUP_LENGTH)
  emit('update:modelValue', digitsOnly)

  if (digitsOnly.length === POSTAL_CODE_LOOKUP_LENGTH) {
    isSearching.value = true
    isOpen.value = true
    syncMenuPosition()
    void fetchSuggestions(digitsOnly)
    return
  }

  suggestions.value = []
  isSearching.value = false
  isOpen.value = false
  menuStyle.value = null
}

function handleFocus() {
  if (props.disabled) {
    return
  }
  if (blurTimeoutId !== null) {
    clearTimeout(blurTimeoutId)
    blurTimeoutId = null
  }
  if (props.modelValue.trim().length === POSTAL_CODE_LOOKUP_LENGTH && suggestions.value.length > 1) {
    isOpen.value = true
    syncMenuPosition()
  }
}

function handleBlur() {
  blurTimeoutId = setTimeout(() => {
    isOpen.value = false
    menuStyle.value = null
    blurTimeoutId = null
  }, blurCloseDelayMs)
}

function handleKeydown(event: KeyboardEvent) {
  if (!isOpen.value || suggestions.value.length === 0) {
    return
  }
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    activeIndex.value = (activeIndex.value + 1) % suggestions.value.length
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    activeIndex.value = activeIndex.value <= 0 ? suggestions.value.length - 1 : activeIndex.value - 1
  } else if (event.key === 'Enter' && activeIndex.value >= 0) {
    event.preventDefault()
    const suggestion = suggestions.value[activeIndex.value]
    if (suggestion) {
      selectSuggestion(suggestion)
    }
  } else if (event.key === 'Escape') {
    isOpen.value = false
    menuStyle.value = null
  }
}

function selectSuggestion(suggestion: PostalCodeCitySuggestion) {
  emit('select', suggestion)
  isOpen.value = false
  menuStyle.value = null
  activeIndex.value = -1
}
</script>
