import type { ContactTopicOption } from '~/types/ContactMessage'
import type { ContactShortcut } from '~/types/GoupixDexContactPage'

export const CONTACT_TOPICS: ContactTopicOption[] = [
  {
    value: 'access',
    label: 'Accès à GoupixDex',
    messagePlaceholder:
      "Dites-moi comment vous vendez vos cartes aujourd'hui (Vinted, eBay, Leboncoin…) et ce que vous attendez de GoupixDex.",
  },
  {
    value: 'help',
    label: "Aide à l'utilisation",
    messagePlaceholder: "Ce que vous essayez de faire et, si possible, l'adresse e-mail de votre compte.",
  },
  {
    value: 'bug',
    label: 'Signaler un bug',
    messagePlaceholder:
      "Ce que vous faisiez, ce qui s'est passé, et sur quel appareil (web, Windows, macOS, téléphone).",
  },
  {
    value: 'privacy',
    label: 'Données personnelles',
    messagePlaceholder: 'Précisez votre demande : accès, correction ou suppression de vos données.',
  },
  {
    value: 'other',
    label: 'Autre',
    messagePlaceholder: 'Votre message.',
  },
]

export const CONTACT_SHORTCUTS: ContactShortcut[] = [
  {
    to: '/request',
    icon: 'i-lucide-key-round',
    title: "Demander l'accès",
    description: 'GoupixDex est gratuit et ouvert sur demande : réponse sous 24 h.',
  },
  {
    to: '/#comment-ca-marche',
    icon: 'i-lucide-route',
    title: 'Comment ça marche',
    description: 'Du scan de la carte à la vente, en six étapes.',
  },
  {
    to: '/login',
    icon: 'i-lucide-log-in',
    title: 'Déjà inscrit ?',
    description: 'Connectez-vous pour retrouver votre stock, vos annonces et votre collection.',
  },
]
