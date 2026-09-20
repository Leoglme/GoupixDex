export type PostalCodeCitySuggestion = {
  nom: string
  codesPostaux: string[]
}

export type PostalCodeAutocompleteInputProps = {
  modelValue: string
  placeholder?: string
  inputId?: string
  required?: boolean
  disabled?: boolean
  teleportToBody?: boolean
}
