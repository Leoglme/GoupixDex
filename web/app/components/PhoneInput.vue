<script setup lang="ts">
/**
 * Champ téléphone international (doc Nuxt UI : UFieldGroup + USelectMenu + UInput + maska).
 * Émet un numéro au format E.164 (`+33612345678`).
 */
import { vMaska } from 'maska/vue'

import type { PhoneCode } from '~/types/phone-code'

const props = withDefaults(
  defineProps<{
    modelValue: string
    defaultCountryCode?: string
    name?: string
    id?: string
    disabled?: boolean
    fixed?: boolean
    autocomplete?: string
  }>(),
  {
    defaultCountryCode: 'FR',
    fixed: true,
    autocomplete: 'tel-national'
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const countryCode = ref(props.defaultCountryCode)
const phone = ref('')
const syncing = ref(false)

const { data: phoneCodes, status, execute } = useLazyFetch<PhoneCode[]>('/api/phone-codes.json', {
  key: 'api-phone-codes',
  immediate: false
})

const country = computed(() => phoneCodes.value?.find(c => c.code === countryCode.value))
const dialCode = computed(() => country.value?.dialCode || '+33')
const mask = computed(() => country.value?.mask || '# ## ## ## ##')

function onOpen(open: boolean) {
  if (open && !phoneCodes.value?.length) {
    execute()
  }
}

watch(countryCode, () => {
  phone.value = ''
})

function buildE164(): string {
  const cc = dialCode.value.replace(/\D/g, '')
  const national = phone.value.replace(/\D/g, '')
  if (!cc || !national) {
    return ''
  }
  return `+${cc}${national}`
}

function hydrateFromE164(value: string) {
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
    const sorted = [...list].sort(
      (a, b) => b.dialCode.replace(/\D/g, '').length - a.dialCode.replace(/\D/g, '').length
    )
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
  }
)

onMounted(async () => {
  await execute()
  if (props.modelValue) {
    hydrateFromE164(props.modelValue)
  }
})
</script>

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
        loading: status === 'pending'
      }"
      :filter-fields="['name', 'code', 'dialCode']"
      :content="{ align: 'start' }"
      :ui="{
        base: 'pe-8',
        content: 'w-48',
        placeholder: 'hidden',
        trailingIcon: 'size-4'
      }"
      trailing-icon="i-lucide-chevrons-up-down"
      @update:open="onOpen"
    >
      <span class="size-5 flex items-center text-lg">
        {{ country?.emoji || '🇫🇷' }}
      </span>

      <template #item-leading="{ item }">
        <span class="size-5 flex items-center text-lg">
          {{ item.emoji }}
        </span>
      </template>

      <template #item-label="{ item }">
        {{ item.name }} ({{ item.dialCode }})
      </template>
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
        leading: 'pointer-events-none text-base md:text-sm text-muted'
      }"
    >
      <template #leading>
        {{ dialCode }}
      </template>
    </UInput>
  </UFieldGroup>
</template>
