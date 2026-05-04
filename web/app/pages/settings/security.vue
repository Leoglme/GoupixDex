<template>
  <UPageCard title="Password" description="Confirm your current password before setting a new one." variant="subtle">
    <UForm :schema="passwordSchema" :state="password" :validate="validate" class="flex max-w-xs flex-col gap-4">
      <UFormField name="current">
        <GoupixDexPasswordInput v-model="password.current" placeholder="Current password" />
      </UFormField>

      <UFormField name="new">
        <GoupixDexPasswordInput v-model="password.new" placeholder="New password" />
      </UFormField>

      <UButton label="Update" class="w-fit" type="submit" />
    </UForm>
  </UPageCard>

  <UPageCard
    title="Account"
    description="No longer want to use our service? You can delete your account here. This action is not reversible. All information related to this account will be deleted permanently."
    class="from-error/10 to-default bg-linear-to-tl from-5%"
  >
    <template #footer>
      <UButton label="Delete account" color="error" />
    </template>
  </UPageCard>
</template>

<script setup lang="ts">
import * as z from 'zod'
import type { FormError } from '@nuxt/ui'

useGoupixPageSeo(
  'Paramètres — sécurité',
  "Mettez à jour votre mot de passe GoupixDex et sécurisez l'accès à votre espace marchand.",
)

const passwordSchema = z.object({
  current: z.string().min(8, 'Must be at least 8 characters'),
  new: z.string().min(8, 'Must be at least 8 characters'),
})

type PasswordSchema = z.output<typeof passwordSchema>

const password = reactive<Partial<PasswordSchema>>({
  current: '',
  new: '',
})

const validate = (state: Partial<PasswordSchema>): FormError[] => {
  const errors: FormError[] = []
  if (state.current && state.new && state.current === state.new) {
    errors.push({ name: 'new', message: 'Passwords must be different' })
  }
  return errors
}
</script>
