<template>
  <GoupixDexLegalDocument
    document-id="legal"
    title="Mentions légales"
    intro="Qui édite GoupixDex, où l'application est hébergée et comment joindre son éditeur."
  >
    <GoupixDexLegalSection title="Éditeur">
      <dl class="app-card grid px-4 sm:px-5">
        <GoupixDexLegalDetailRow label="Éditeur">{{ PUBLISHER.fullName }}</GoupixDexLegalDetailRow>
        <GoupixDexLegalDetailRow label="Statut">{{ PUBLISHER.legalStatus }}</GoupixDexLegalDetailRow>
        <GoupixDexLegalDetailRow label="Adresse">{{ PUBLISHER.address }}</GoupixDexLegalDetailRow>
        <GoupixDexLegalDetailRow label="SIRET">{{ PUBLISHER.siret }}</GoupixDexLegalDetailRow>
        <GoupixDexLegalDetailRow label="N° de TVA">
          {{ PUBLISHER.vatNumber }}
          <span class="text-muted block text-sm">TVA non applicable, art. 293 B du CGI</span>
        </GoupixDexLegalDetailRow>
        <GoupixDexLegalDetailRow label="Téléphone">{{ PUBLISHER.phone }}</GoupixDexLegalDetailRow>
        <GoupixDexLegalDetailRow label="E-mail">{{ PUBLISHER.email }}</GoupixDexLegalDetailRow>
      </dl>
    </GoupixDexLegalSection>

    <GoupixDexLegalSection title="Directeur de la publication">
      <p>{{ PUBLISHER.fullName }}</p>
    </GoupixDexLegalSection>

    <GoupixDexLegalSection title="Hébergement">
      <p>Le site et l'application GoupixDex sont hébergés par :</p>
      <dl class="app-card grid px-4 sm:px-5">
        <GoupixDexLegalDetailRow label="Hébergeur">{{ HOSTING_PROVIDER.name }}</GoupixDexLegalDetailRow>
        <GoupixDexLegalDetailRow label="Adresse">{{ HOSTING_PROVIDER.address }}</GoupixDexLegalDetailRow>
        <GoupixDexLegalDetailRow label="Téléphone">{{ HOSTING_PROVIDER.phone }}</GoupixDexLegalDetailRow>
        <GoupixDexLegalDetailRow label="Site">{{ HOSTING_PROVIDER.website }}</GoupixDexLegalDetailRow>
      </dl>
    </GoupixDexLegalSection>

    <GoupixDexLegalSection title="Propriété intellectuelle">
      <p>
        Le nom GoupixDex, son logo, les textes, les visuels et le code de l'application appartiennent à
        {{ PUBLISHER.fullName }}. Toute reproduction, même partielle, demande son accord écrit.
      </p>
      <p>
        Pokémon, le nom des cartes et leurs illustrations appartiennent à Nintendo, Creatures Inc., GAME FREAK inc. et
        The Pokémon Company. GoupixDex n'est ni affilié à ces sociétés, ni approuvé par elles : les visuels des cartes
        servent uniquement à reconnaître les cartes que vous possédez ou vendez.
      </p>
      <p>
        Vinted, eBay, Leboncoin, Cardmarket et Amazon sont des marques de leurs propriétaires respectifs. GoupixDex
        n'est affilié à aucune de ces plateformes.
      </p>
      <p>Les polices Fredoka, Nunito Sans et JetBrains Mono sont utilisées sous licence SIL Open Font License.</p>
    </GoupixDexLegalSection>

    <GoupixDexLegalSection title="Données personnelles">
      <p>
        Les données traitées par GoupixDex, leur usage et vos droits sont décrits dans la
        <NuxtLink to="/privacy" class="landing-link">politique de confidentialité</NuxtLink>.
      </p>
    </GoupixDexLegalSection>

    <GoupixDexLegalSection title="Signaler un contenu">
      <p>
        Pour signaler un contenu illicite ou une erreur, écrivez à
        <a :href="PUBLISHER.emailHref" class="landing-link">{{ PUBLISHER.email }}</a> ou appelez le
        <a :href="PUBLISHER.phoneHref" class="landing-link whitespace-nowrap">{{ PUBLISHER.phone }}</a
        >.
      </p>
    </GoupixDexLegalSection>
  </GoupixDexLegalDocument>
</template>

<script lang="ts" setup>
import { HOSTING_PROVIDER, PUBLISHER } from '~/utils/publisher'

definePageMeta({
  layout: 'landing',
})

useGoupixPageSeo(
  'Mentions légales',
  "Éditeur, hébergeur et contact de GoupixDex, l'atelier des vendeurs de cartes Pokémon TCG.",
)
</script>
