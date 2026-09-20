import { Faker, fr } from '@faker-js/faker'

const frFaker = new Faker({ locale: [fr] })

/**
 * Name sent to Amazon registration: profile full name, or a plausible French fake name.
 */
export function resolveAmazonProvisionCustomerName(fullName: string | null | undefined): string {
  const trimmed = (fullName ?? '').trim()
  if (trimmed.length >= 2) {
    return trimmed.slice(0, 120)
  }
  return `${frFaker.person.firstName()} ${frFaker.person.lastName()}`
}
