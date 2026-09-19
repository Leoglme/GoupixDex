import type {
  AmazonAccountCreatePayload,
  AmazonAccountCredentials,
  AmazonAccountUpdatePayload,
  AmazonAccountsOverview,
  AmazonVaultAccount,
} from '~/types/amazonAccounts'

/**
 * Remote vault for Amazon.fr credentials (encrypted at rest on the API).
 */
export function useAmazonAccounts() {
  const { $api } = useNuxtApp()

  /**
   *
   */
  async function fetchOverview(): Promise<AmazonAccountsOverview> {
    const { data } = await $api.get<AmazonAccountsOverview>('/amazon-accounts')
    return data
  }

  /**
   *
   */
  async function setActiveAccount(accountId: number | null): Promise<AmazonAccountsOverview> {
    const { data } = await $api.put<AmazonAccountsOverview>('/amazon-accounts/active', {
      account_id: accountId,
    })
    return data
  }

  /**
   *
   */
  async function createAccount(payload: AmazonAccountCreatePayload): Promise<AmazonVaultAccount> {
    const { data } = await $api.post<AmazonVaultAccount>('/amazon-accounts', payload)
    return data
  }

  /**
   *
   */
  async function updateAccount(id: number, payload: AmazonAccountUpdatePayload): Promise<AmazonVaultAccount> {
    const { data } = await $api.put<AmazonVaultAccount>(`/amazon-accounts/${id}`, payload)
    return data
  }

  /**
   *
   */
  async function deleteAccount(id: number): Promise<void> {
    await $api.delete(`/amazon-accounts/${id}`)
  }

  /**
   *
   */
  async function revealCredentials(id: number): Promise<AmazonAccountCredentials> {
    const { data } = await $api.get<AmazonAccountCredentials>(`/amazon-accounts/${id}/credentials`)
    return data
  }

  return {
    fetchOverview,
    setActiveAccount,
    createAccount,
    updateAccount,
    deleteAccount,
    revealCredentials,
  }
}
