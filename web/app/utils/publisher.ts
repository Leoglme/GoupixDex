import type { HostingProvider, PublisherIdentity } from '~/types/Publisher'

export const PUBLISHER: PublisherIdentity = {
  fullName: 'Léo Guillaume',
  legalStatus: 'Entrepreneur individuel (micro-entreprise), nom commercial Dibodev',
  address: '6 rue Simone Morand, Apt A13, 35230 Saint-Erblon, France',
  city: 'Saint-Erblon, près de Rennes',
  siret: '988 307 906 00020',
  vatNumber: 'FR02 988 307 906',
  email: 'contact@dibodev.fr',
  emailHref: 'mailto:contact@dibodev.fr',
  phone: '06 42 19 38 12',
  phoneHref: 'tel:+33642193812',
  websiteUrl: 'https://dibodev.fr',
  websiteLabel: 'dibodev.fr',
  portraitSrc: '/images/contact/leo-guillaume.webp',
}

export const HOSTING_PROVIDER: HostingProvider = {
  name: 'OVH SAS',
  address: '2 rue Kellermann, 59100 Roubaix, France',
  phone: '1007',
  website: 'ovhcloud.com',
}
