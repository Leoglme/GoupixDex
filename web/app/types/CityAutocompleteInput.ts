export type CitySuggestion = {
  code: string
  nom: string
  codeDepartement?: string
  codesPostaux?: string[]
}

export type CityAutocompleteInputProps = {
  modelValue: string
  placeholder?: string
  inputId?: string
  required?: boolean
  disabled?: boolean
  teleportToBody?: boolean
}
