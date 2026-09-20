import { Faker, fr } from '@faker-js/faker'

const frFaker = new Faker({ locale: [fr] })

const PASSWORD_CHARS = 'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%&*'

/** MX Resend — domaine fixe pour les adresses générées à la création Amazon. */
export const AMAZON_PROVISION_EMAIL_DOMAIN = 'mail.goupixdex.dibodev.fr'

export function generateAmazonProvisionPassword(length = 18): string {
  const bytes = new Uint8Array(length)
  crypto.getRandomValues(bytes)
  let out = ''
  for (let i = 0; i < length; i++) {
    out += PASSWORD_CHARS[bytes[i]! % PASSWORD_CHARS.length]
  }
  return out
}

function emailLocalSlug(value: string): string {
  return value
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '')
}

/** Prénom.nom + chiffres discrets — même domaine, aspect boîte perso. */
export function generateAmazonProvisionEmailLocalPart(): string {
  const first = emailLocalSlug(frFaker.person.firstName())
  const last = emailLocalSlug(frFaker.person.lastName())
  const suffix = 10 + (crypto.getRandomValues(new Uint8Array(1))[0]! % 90)
  const base = [first, last].filter(Boolean).join('.') || 'compte'
  return `${base}${suffix}`
}

/** Adresse unique sur le domaine GoupixDex (réception MX / Resend). */
export function generateAmazonProvisionEmail(): string {
  return `${generateAmazonProvisionEmailLocalPart()}@${AMAZON_PROVISION_EMAIL_DOMAIN}`
}
