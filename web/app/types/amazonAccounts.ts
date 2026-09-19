export interface AmazonVaultAccount {
  id: number
  label: string | null
  amazon_email: string
  has_password: boolean
  created_at: string
  updated_at: string
}

export interface AmazonAccountsOverview {
  accounts: AmazonVaultAccount[]
  active_account_id: number | null
}

export interface AmazonAccountCreatePayload {
  label?: string | null
  amazon_email: string
  password: string
}

export interface AmazonAccountUpdatePayload {
  label?: string | null
  amazon_email?: string
  password?: string
  clear_password?: boolean
}

export interface AmazonAccountCredentials {
  amazon_email: string
  password: string
}
