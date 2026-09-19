const PASSWORD_CHARS = 'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%&*'

/** Inboxes @1secmail.* (pas de config ; lecture possible via leur API si besoin plus tard). */
const DISPOSABLE_EMAIL_DOMAINS = ['1secmail.com', '1secmail.org', '1secmail.net'] as const

export function generateAmazonProvisionPassword(length = 18): string {
  const bytes = new Uint8Array(length)
  crypto.getRandomValues(bytes)
  let out = ''
  for (let i = 0; i < length; i++) {
    out += PASSWORD_CHARS[bytes[i]! % PASSWORD_CHARS.length]
  }
  return out
}

export function generateAmazonProvisionEmail(): string {
  const login = crypto.randomUUID().replace(/-/g, '').slice(0, 14)
  const domain =
    DISPOSABLE_EMAIL_DOMAINS[crypto.getRandomValues(new Uint8Array(1))[0]! % DISPOSABLE_EMAIL_DOMAINS.length]!
  return `${login}@${domain}`
}
