export type AddressSuggestion = {
  label: string
  name: string
  postcode: string
  city: string
}

export type AddressAutocompleteInputProps = {
  modelValue: string
  placeholder?: string
  inputId?: string
  required?: boolean
  disabled?: boolean
  /** false dans les drawers pour ne pas masquer le pied de panneau */
  teleportToBody?: boolean
}

export type UiAddressAutocompleteInputEmits = {
  'update:modelValue': [value: string]
  select: [suggestion: AddressSuggestion]
}
