<template>
  <div class="app-card min-w-0 self-start">
    <div class="flex items-center gap-4 p-5 sm:p-6">
      <img
        :src="PUBLISHER.portraitSrc"
        :alt="`Portrait de ${PUBLISHER.fullName}`"
        width="64"
        height="64"
        class="size-16 shrink-0 rounded-full bg-(--app-surface-2) object-cover"
      />
      <div class="min-w-0">
        <p class="font-display text-highlighted text-lg leading-tight font-semibold">{{ PUBLISHER.fullName }}</p>
        <p class="text-muted mt-0.5 text-sm">Développeur de GoupixDex</p>
        <a
          :href="PUBLISHER.websiteUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="landing-link mt-1 inline-flex items-center gap-1 text-sm"
        >
          {{ PUBLISHER.websiteLabel }}
          <UIcon name="i-lucide-external-link" class="size-3.5" aria-hidden="true" />
        </a>
      </div>
    </div>

    <div class="border-t border-(--app-line) p-5 sm:p-6">
      <p class="app-label">Par e-mail</p>
      <a
        :href="PUBLISHER.emailHref"
        class="font-display text-highlighted mt-2 block text-2xl leading-tight font-semibold break-words transition-colors hover:text-(--app-accent)"
      >
        {{ PUBLISHER.email }}
      </a>
      <p class="text-muted mt-2 text-sm leading-relaxed">Réponse sous 24 h, du lundi au vendredi.</p>
      <div class="mt-4 flex flex-wrap gap-2">
        <UButton :to="PUBLISHER.emailHref" color="neutral" variant="outline" icon="i-lucide-mail">
          Écrire un e-mail
        </UButton>
        <GoupixDexCopyButton :value="PUBLISHER.email" label="Copier l'adresse" />
      </div>
    </div>

    <div class="border-t border-(--app-line) p-5 sm:p-6">
      <p class="app-label">Par téléphone</p>
      <a
        :href="PUBLISHER.phoneHref"
        class="font-display text-highlighted mt-2 block text-3xl leading-tight font-semibold tabular-nums transition-colors hover:text-(--app-accent)"
      >
        {{ PUBLISHER.phone }}
      </a>
      <p class="text-muted mt-2 text-sm leading-relaxed">
        Du lundi au vendredi, de 9 h à 18 h. Pas de standard : vous tombez directement sur moi.
      </p>
      <div class="mt-4 flex flex-wrap gap-2">
        <UButton :to="PUBLISHER.phoneHref" color="neutral" variant="outline" icon="i-lucide-phone"> Appeler </UButton>
        <GoupixDexCopyButton :value="PUBLISHER.phone" label="Copier le numéro" />
      </div>
    </div>

    <div class="border-t border-(--app-line) p-5 sm:p-6">
      <p class="app-label">Basé à</p>
      <p class="font-display text-highlighted mt-2 text-lg font-semibold">{{ PUBLISHER.city }}</p>
      <p class="text-muted mt-2 text-sm leading-relaxed">
        GoupixDex est édité par Dibodev, l'entreprise de {{ PUBLISHER.fullName }}.
        <NuxtLink to="/legal" class="landing-link">Mentions légales</NuxtLink>
      </p>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { PUBLISHER } from '~/utils/publisher'
</script>
