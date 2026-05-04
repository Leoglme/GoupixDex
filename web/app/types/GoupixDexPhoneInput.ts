/**
 * Props for {@link ~/components/GoupixDexPhoneInput.vue}.
 * International phone field (Nuxt UI + maska); emits E.164 (`+33612345678`).
 */
export interface GoupixDexPhoneInputProps {
  /** v-model: full international number in E.164 form */
  modelValue: string
  /** ISO 3166-1 alpha-2 country code used for the default dial prefix */
  defaultCountryCode?: string
  /** Passed to the tel `<input>` (`name`) */
  name?: string
  /** Passed to the tel `<input>` (`id`) */
  id?: string
  /** Disables country select + input */
  disabled?: boolean
  /** UInput mask fixed mode (maska) */
  fixed?: boolean
  /** Native `autocomplete` hint on the tel input */
  autocomplete?: string
}

/** Emit function for {@link ~/components/GoupixDexPhoneInput.vue} (v-model → E.164). */
export type GoupixDexPhoneInputEmit = (e: 'update:modelValue', value: string) => void
