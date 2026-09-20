import type { AddressSuggestion } from '~/types/AddressAutocompleteInput'
import type { PostalCodeCitySuggestion } from '~/types/PostalCodeAutocompleteInput'

type BanFeatureProperties = {
  label?: string
  name?: string
  postcode?: string
  city?: string
}

type BanFeature = {
  properties?: BanFeatureProperties
}

type BanSearchResponse = {
  features?: BanFeature[]
}

const DEFAULT_ADDRESS_LIMIT = 6
const POSTAL_CODE_LENGTH = 5

type CommuneByPostalCode = {
  nom?: string
  codesPostaux?: string[]
}

/**
 * Recherche d’adresses via la Base Adresse Nationale (BAN).
 */
export async function searchAddressSuggestions(
  query: string,
  limit: number = DEFAULT_ADDRESS_LIMIT,
): Promise<AddressSuggestion[]> {
  const trimmedQuery = query.trim()
  if (trimmedQuery.length < 2) {
    return []
  }

  const response = await $fetch<BanSearchResponse>('https://api-adresse.data.gouv.fr/search/', {
    query: {
      q: trimmedQuery,
      limit,
    },
  })

  return (response.features ?? [])
    .map((feature: BanFeature): AddressSuggestion | null => {
      const properties = feature.properties
      if (!properties?.label || !properties.name || !properties.postcode || !properties.city) {
        return null
      }
      return {
        label: properties.label,
        name: properties.name,
        postcode: properties.postcode,
        city: properties.city,
      }
    })
    .filter((suggestion): suggestion is AddressSuggestion => suggestion !== null)
}

/** Longueur d’un code postal français avant lookup geo.api.gouv.fr. */
export const POSTAL_CODE_LOOKUP_LENGTH = POSTAL_CODE_LENGTH

/**
 * Communes associées à un code postal (geo.api.gouv.fr).
 */
export async function searchCitiesByPostalCode(postalCode: string): Promise<PostalCodeCitySuggestion[]> {
  const trimmedCode = postalCode.trim()
  if (!/^\d{5}$/.test(trimmedCode)) {
    return []
  }

  const communes = await $fetch<CommuneByPostalCode[]>('https://geo.api.gouv.fr/communes', {
    query: {
      codePostal: trimmedCode,
      fields: 'nom,codesPostaux',
      limit: 100,
    },
  })

  return communes
    .filter((commune): commune is PostalCodeCitySuggestion => Boolean(commune.nom))
    .map(
      (commune): PostalCodeCitySuggestion => ({
        nom: commune.nom as string,
        codesPostaux: commune.codesPostaux ?? [trimmedCode],
      }),
    )
    .sort((left, right) => left.nom.localeCompare(right.nom, 'fr'))
}
