<template>
  <UFieldGroup class="w-full">
    <USelectMenu
      v-model="countryCode"
      :items="phoneCodes ?? []"
      value-key="code"
      :disabled="disabled"
      :search-input="{
        placeholder: 'Rechercher un pays…',
        icon: 'i-lucide-search',
        loading: status === 'pending',
      }"
      :filter-fields="['name', 'code', 'dialCode']"
      :content="{ align: 'start' }"
      :ui="{
        base: 'pe-8',
        content: 'w-48',
        placeholder: 'hidden',
        trailingIcon: 'size-4',
      }"
      trailing-icon="i-lucide-chevrons-up-down"
      @update:open="onOpen"
    >
      <span class="flex size-5 items-center text-lg">
        {{ country?.emoji || '🇫🇷' }}
      </span>

      <template #item-leading="{ item }">
        <span class="flex size-5 items-center text-lg">
          {{ item.emoji }}
        </span>
      </template>

      <template #item-label="{ item }"> {{ item.name }} ({{ item.dialCode }}) </template>
    </USelectMenu>

    <UInput
      :id="id"
      v-model="phone"
      v-maska="mask"
      type="tel"
      inputmode="tel"
      :name="name"
      :disabled="disabled"
      :fixed="fixed"
      :autocomplete="autocomplete"
      :placeholder="mask.replaceAll('#', '_')"
      :style="{ '--dial-code-length': `${dialCode.length + 1.5}ch` }"
      class="min-w-0 flex-1"
      :ui="{
        base: 'ps-(--dial-code-length)',
        leading: 'pointer-events-none text-base md:text-sm text-muted',
      }"
    >
      <template #leading>
        {{ dialCode }}
      </template>
    </UInput>
  </UFieldGroup>
</template>

<script setup lang="ts">
import { vMaska } from 'maska/vue'
import type { ComputedRef, Ref } from 'vue'

import type { GoupixDexPhoneInputEmit, GoupixDexPhoneInputProps } from '../types/GoupixDexPhoneInput'
import type { PhoneCode } from '../types/phone-code'

/* Props */
/**
 * Define the GoupixDexPhoneInput props (runtime + TS interface).
 */
const props: GoupixDexPhoneInputProps = defineProps({
  modelValue: {
    type: String,
    required: true,
  },
  defaultCountryCode: {
    type: String,
    default: 'FR',
  },
  name: {
    type: String,
    default: undefined,
  },
  id: {
    type: String,
    default: undefined,
  },
  disabled: {
    type: Boolean,
    default: undefined,
  },
  fixed: {
    type: Boolean,
    default: true,
  },
  autocomplete: {
    type: String,
    default: 'tel-national',
  },
})

/* Emits */
const emit: GoupixDexPhoneInputEmit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

/* Refs */
const countryCode: Ref<string> = ref(props.defaultCountryCode ?? 'FR')
const phone: Ref<string> = ref('')
const syncing: Ref<boolean> = ref(false)

const lazyPhoneCodes = useLazyFetch<PhoneCode[]>('/api/phone-codes.json', {
  key: 'api-phone-codes',
  immediate: false,
})
const phoneCodes: Ref<PhoneCode[] | null | undefined> = lazyPhoneCodes.data
const status = lazyPhoneCodes.status
const execute = lazyPhoneCodes.execute

/* Computed */
const country: ComputedRef<PhoneCode | undefined> = computed(() =>
  phoneCodes.value?.find((c) => c.code === countryCode.value),
)
const dialCode: ComputedRef<string> = computed(() => country.value?.dialCode || '+33')
const mask: ComputedRef<string> = computed(() => country.value?.mask || '# ## ## ## ##')

/* Functions */
/**
 * Fetch phone code list when the country menu opens (lazy).
 * @param open - Select menu open state
 * @returns {void} Nothing
 */
function onOpen(open: boolean): void {
  if (open && !phoneCodes.value?.length) {
    execute()
  }
}

/**
 * Build E.164 value from the current dial code and national digits.
 * @returns {string} E.164 string, or empty when incomplete
 */
function buildE164(): string {
  const cc = dialCode.value.replace(/\D/g, '')
  const national = phone.value.replace(/\D/g, '')
  if (!cc || !national) {
    return ''
  }
  return `+${cc}${national}`
}

/**
 * Parse an E.164 string and update country + national parts (internal sync guard).
 * @param value - Incoming model value (`modelValue`)
 * @returns {void} Nothing
 */
function hydrateFromE164(value: string): void {
  const list = phoneCodes.value
  if (!list?.length) {
    return
  }
  syncing.value = true
  try {
    if (!value?.trim()) {
      phone.value = ''
      return
    }
    const digits = value.replace(/\D/g, '')
    if (!digits) {
      return
    }
    const sorted = [...list].sort((a, b) => b.dialCode.replace(/\D/g, '').length - a.dialCode.replace(/\D/g, '').length)
    for (const c of sorted) {
      const cc = c.dialCode.replace(/\D/g, '')
      if (digits.startsWith(cc)) {
        countryCode.value = c.code
        phone.value = digits.slice(cc.length)
        return
      }
    }
  } finally {
    nextTick(() => {
      syncing.value = false
    })
  }
}

/* Watchers */
watch(countryCode, () => {
  phone.value = ''
})

watch([countryCode, phone], () => {
  if (syncing.value) {
    return
  }
  const next = buildE164()
  if (next !== props.modelValue) {
    emit('update:modelValue', next)
  }
})

watch(
  () => props.modelValue,
  (v) => {
    if (syncing.value || !phoneCodes.value?.length) {
      return
    }
    const cur = buildE164()
    if (v === cur) {
      return
    }
    hydrateFromE164(v || '')
  },
)

/* Lifecycle */
onMounted(async () => {
  await execute()
  if (props.modelValue) {
    hydrateFromE164(props.modelValue)
  }
})
</script>
