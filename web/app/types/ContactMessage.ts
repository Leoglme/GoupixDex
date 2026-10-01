export type ContactTopic = 'access' | 'help' | 'bug' | 'privacy' | 'other'

export type ContactTopicOption = {
  value: ContactTopic
  label: string
  messagePlaceholder: string
}

export type ContactMessagePayload = {
  topic: ContactTopic
  name: string
  email: string
  phone: string | null
  message: string
  website: string
}

export type UseContactMessage = {
  sendContactMessage: (payload: ContactMessagePayload) => Promise<void>
}
