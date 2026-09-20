export interface UserProfilePayload {
  id: number
  email: string
  full_name: string | null
  sender_line1: string | null
  sender_line2: string | null
  sender_postal_code: string | null
  sender_city: string | null
  sender_address_complete: boolean
  phone_e164: string | null
  amazon_provision_profile_complete: boolean
}
