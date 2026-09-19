<template>
  <UCard>
    <template #header>
      <p class="text-highlighted font-medium">Amazon (invitations)</p>
    </template>
    <p class="text-muted text-sm">
      Les comptes Amazon et les invitations se gèrent sur la page
      <NuxtLink to="/amazon-invites" class="text-primary font-medium hover:underline"> Invitations Amazon </NuxtLink>
      (bouton « Comptes » en haut de page).
    </p>
    <UButton class="mt-3" color="primary" variant="soft" icon="i-simple-icons-amazon" to="/amazon-invites?accounts=1">
      Ouvrir Invitations Amazon
    </UButton>
  </UCard>
</template>
