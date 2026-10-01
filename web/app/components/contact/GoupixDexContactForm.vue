<template>
  <div
    class="min-w-0 border-t border-(--app-line) pt-8 sm:rounded-xl sm:border sm:bg-(--app-surface) sm:p-8 lg:self-start lg:p-10"
  >
    <div v-if="sentMessage" class="grid justify-items-start gap-4">
      <span class="flex size-12 items-center justify-center rounded-full bg-(--app-green-soft) text-(--app-green)">
        <UIcon name="i-lucide-check" class="size-6" aria-hidden="true" />
      </span>
      <h2
        ref="confirmationHeading"
        tabindex="-1"
        class="font-display text-highlighted text-2xl font-semibold focus:outline-none"
      >
        Message envoyé !
      </h2>
      <p class="text-muted text-base leading-relaxed">
        Merci {{ sentMessage.firstName }}. Je vous réponds sous 24 h en semaine, à
        <strong class="text-highlighted">{{ sentMessage.email }}</strong
        >.
      </p>
      <UButton color="neutral" variant="outline" icon="i-lucide-pen-line" @click="startNewMessage">
        Écrire un autre message
      </UButton>
    </div>

    <form v-else class="grid gap-6" novalidate @submit.prevent="submitMessage">
      <div class="grid gap-1.5">
        <h2 class="font-display text-highlighted text-2xl font-semibold">Écrivez-moi</h2>
        <p class="text-muted text-sm">Tous les champs sont obligatoires, sauf le téléphone.</p>
      </div>

      <fieldset class="min-w-0">
        <legend class="text-highlighted mb-3 text-sm font-semibold">Votre message concerne</legend>
        <div class="flex flex-wrap gap-2">
          <label
            v-for="topic in CONTACT_TOPICS"
            :key="topic.value"
            class="cursor-pointer rounded-full border px-4 py-2 text-sm font-semibold transition-colors has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-(--app-accent)"
            :class="
              selectedTopic === topic.value
                ? 'border-(--app-accent) bg-(--app-accent-soft) text-(--app-accent-ink)'
                : 'text-muted border-(--app-line) bg-(--app-surface) hover:border-(--app-ink-soft) hover:text-(--app-ink)'
            "
          >
            <input v-model="selectedTopic" type="radio" name="topic" :value="topic.value" class="sr-only" />
            {{ topic.label }}
          </label>
        </div>
      </fieldset>

      <div class="grid gap-6 sm:grid-cols-2 sm:gap-4">
        <UFormField label="Nom" :error="nameError">
          <UInput
            id="contact-name"
            v-model="visitorName"
            name="name"
            autocomplete="name"
            :maxlength="120"
            placeholder="Camille Martin"
            size="xl"
            class="w-full"
          />
        </UFormField>
        <UFormField label="E-mail" :error="emailError">
          <UInput
            id="contact-email"
            v-model="visitorEmail"
            type="email"
            name="email"
            inputmode="email"
            autocomplete="email"
            :maxlength="254"
            placeholder="vous@exemple.fr"
            size="xl"
            class="w-full"
          />
        </UFormField>
      </div>

      <UFormField label="Téléphone" hint="Facultatif" help="Si vous préférez que je vous rappelle.">
        <UInput
          id="contact-phone"
          v-model="visitorPhone"
          type="tel"
          name="phone"
          autocomplete="tel"
          :maxlength="40"
          placeholder="06 12 34 56 78"
          size="xl"
          class="w-full"
        />
      </UFormField>

      <UFormField label="Message" :error="messageError">
        <UTextarea
          id="contact-message"
          v-model="visitorMessage"
          name="message"
          :rows="6"
          :maxlength="5000"
          :placeholder="messagePlaceholder"
          size="xl"
          class="w-full"
        />
      </UFormField>

      <div class="absolute -left-[10000px] h-px w-px overflow-hidden" aria-hidden="true">
        <input
          id="contact-website"
          v-model="honeypotValue"
          type="text"
          name="website"
          tabindex="-1"
          autocomplete="off"
        />
      </div>

      <GoupixDexAlert
        v-if="sendingErrorMessage"
        variant="error"
        title="Votre message n'est pas parti."
        :description="sendingErrorMessage"
      />

      <div class="grid gap-4">
        <UButton
          type="submit"
          color="primary"
          size="xl"
          block
          :loading="isSending"
          trailing-icon="i-lucide-arrow-right"
        >
          Envoyer le message
        </UButton>
        <p class="text-muted text-xs leading-relaxed">
          Vos coordonnées servent uniquement à vous répondre.
          <NuxtLink to="/privacy" class="landing-link">Politique de confidentialité</NuxtLink>
        </p>
      </div>
    </form>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, Ref } from 'vue'
import type { ContactTopic, ContactTopicOption, UseContactMessage } from '~/types/ContactMessage'
import type { ContactSentMessage } from '~/types/GoupixDexContactForm'
import { isAxiosError } from 'axios'
import { CONTACT_TOPICS } from '~/utils/contactPage'
import { isEmailAddress, isFieldFilled } from '~/utils/formFields'
import { PUBLISHER } from '~/utils/publisher'

const { sendContactMessage }: UseContactMessage = useContactMessage()

const selectedTopic: Ref<ContactTopic> = ref('access')
const visitorName: Ref<string> = ref('')
const visitorEmail: Ref<string> = ref('')
const visitorPhone: Ref<string> = ref('')
const visitorMessage: Ref<string> = ref('')
const honeypotValue: Ref<string> = ref('')
const hasTriedToSubmit: Ref<boolean> = ref(false)
const isSending: Ref<boolean> = ref(false)
const sendingErrorMessage: Ref<string | null> = ref(null)
const sentMessage: Ref<ContactSentMessage | null> = ref(null)
const confirmationHeading: Ref<HTMLHeadingElement | null> = ref(null)

const nameError: ComputedRef<string | undefined> = computed((): string | undefined =>
  hasTriedToSubmit.value && !isFieldFilled(visitorName.value)
    ? 'Indiquez votre nom pour que je sache à qui je réponds.'
    : undefined,
)
const emailError: ComputedRef<string | undefined> = computed((): string | undefined =>
  hasTriedToSubmit.value && !isEmailAddress(visitorEmail.value)
    ? "Indiquez un e-mail valide : c'est là que je vous réponds."
    : undefined,
)
const messageError: ComputedRef<string | undefined> = computed((): string | undefined =>
  hasTriedToSubmit.value && !isFieldFilled(visitorMessage.value)
    ? 'Écrivez votre message (quelques mots suffisent).'
    : undefined,
)
const messagePlaceholder: ComputedRef<string> = computed(
  (): string =>
    CONTACT_TOPICS.find((topic: ContactTopicOption): boolean => topic.value === selectedTopic.value)
      ?.messagePlaceholder ?? '',
)

/**
 * Identifiant du premier champ à corriger, dans l'ordre de lecture.
 * @returns {string | null} L'identifiant du champ, ou null quand tout est rempli.
 */
function findFirstInvalidFieldId(): string | null {
  if (nameError.value) return 'contact-name'
  if (emailError.value) return 'contact-email'
  if (messageError.value) return 'contact-message'
  return null
}

/**
 * Vérifie les champs, envoie le message, puis affiche la confirmation ou l'échec.
 * @returns {Promise<void>} Résolue une fois la confirmation ou l'erreur affichée.
 */
async function submitMessage(): Promise<void> {
  hasTriedToSubmit.value = true
  sendingErrorMessage.value = null
  const invalidFieldId: string | null = findFirstInvalidFieldId()
  if (invalidFieldId) {
    document.getElementById(invalidFieldId)?.focus()
    return
  }
  const trimmedName: string = visitorName.value.trim()
  const trimmedEmail: string = visitorEmail.value.trim()
  isSending.value = true
  try {
    await sendContactMessage({
      topic: selectedTopic.value,
      name: trimmedName,
      email: trimmedEmail,
      phone: visitorPhone.value.trim() || null,
      message: visitorMessage.value.trim(),
      website: honeypotValue.value,
    })
    sentMessage.value = { firstName: trimmedName.split(/\s+/)[0] ?? trimmedName, email: trimmedEmail }
    await nextTick()
    confirmationHeading.value?.focus()
  } catch (error: unknown) {
    const isRateLimited: boolean = isAxiosError(error) && error.response?.status === 429
    sendingErrorMessage.value = isRateLimited
      ? `Plusieurs messages sont partis en peu de temps : réessayez dans une heure, ou écrivez directement à ${PUBLISHER.email}.`
      : `Réessayez dans un instant, ou écrivez directement à ${PUBLISHER.email}.`
  } finally {
    isSending.value = false
  }
}

/**
 * Réaffiche le formulaire pour un autre message, en gardant le nom et l'e-mail du visiteur.
 * @returns {void}
 */
function startNewMessage(): void {
  visitorMessage.value = ''
  hasTriedToSubmit.value = false
  sentMessage.value = null
}
</script>
