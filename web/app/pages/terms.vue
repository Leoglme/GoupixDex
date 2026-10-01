<template>
  <GoupixDexLegalDocument
    document-id="terms"
    title="Conditions d'utilisation"
    intro="En utilisant GoupixDex, sur le web ou dans l'application desktop, vous acceptez les conditions ci-dessous."
  >
    <GoupixDexLegalSection title="Éditeur">
      <p>
        GoupixDex est édité par {{ PUBLISHER.fullName }}, entrepreneur individuel exerçant sous le nom Dibodev, SIRET
        {{ PUBLISHER.siret }}, {{ PUBLISHER.address }}. Contact :
        <a :href="PUBLISHER.emailHref" class="landing-link">{{ PUBLISHER.email }}</a> ou
        <a :href="PUBLISHER.phoneHref" class="landing-link whitespace-nowrap">{{ PUBLISHER.phone }}</a
        >. Le détail figure dans les <NuxtLink to="/legal" class="landing-link">mentions légales</NuxtLink>.
      </p>
    </GoupixDexLegalSection>

    <GoupixDexLegalSection title="Objet du service">
      <p>
        GoupixDex aide les vendeurs de cartes Pokémon TCG à reconnaître leurs cartes, à les estimer avec les prix
        Cardmarket, à préparer et publier leurs annonces sur Vinted, eBay et Leboncoin, puis à suivre leur stock, leurs
        ventes et la valeur de leur collection, sur le web et dans une application pour Windows et macOS.
      </p>
    </GoupixDexLegalSection>

    <GoupixDexLegalSection title="Accès au service">
      <p>
        GoupixDex est gratuit et ouvert sur demande : l'éditeur valide chaque demande d'accès et peut la refuser. Les
        fonctions qui pilotent votre navigateur (Vinted, Leboncoin, Cardmarket, Amazon) demandent l'application desktop.
      </p>
    </GoupixDexLegalSection>

    <GoupixDexLegalSection title="Compte">
      <p>
        Vous êtes responsable de la confidentialité de vos identifiants et de l'activité réalisée depuis votre compte.
        Prévenez l'éditeur sans attendre si vous pensez qu'un tiers y a accès.
      </p>
    </GoupixDexLegalSection>

    <GoupixDexLegalSection title="Vos annonces et les plateformes">
      <p>
        Vous restez le vendeur : le contenu, le prix et l'état annoncés de vos cartes, comme la relation avec vos
        acheteurs, relèvent de votre responsabilité. Vous utilisez vos propres comptes Vinted, eBay, Leboncoin,
        Cardmarket et Amazon, dans le respect de leurs conditions d'utilisation.
      </p>
      <p>
        GoupixDex n'est affilié à aucune de ces plateformes et ne répond pas de leurs décisions, comme la limitation ou
        la fermeture d'un compte.
      </p>
    </GoupixDexLegalSection>

    <GoupixDexLegalSection title="Prix et reconnaissance des cartes">
      <p>
        Les prix affichés (Cardmarket, TCGPlayer, eBay) sont des références indicatives tirées de sources publiques :
        ils ne garantissent ni un prix de vente, ni la valeur d'une carte. La reconnaissance automatique peut se tromper
        : vérifiez chaque annonce avant de la publier.
      </p>
    </GoupixDexLegalSection>

    <GoupixDexLegalSection title="Disponibilité et responsabilité">
      <p>
        GoupixDex est fourni « en l'état », sans garantie de disponibilité continue : ses fonctions et ses intégrations
        peuvent évoluer ou s'interrompre, notamment quand une plateforme change son fonctionnement.
      </p>
      <p>
        Le service étant gratuit, la responsabilité de l'éditeur ne peut être engagée pour une perte de données, une
        vente manquée ou un dommage indirect, dans les limites permises par la loi.
      </p>
    </GoupixDexLegalSection>

    <GoupixDexLegalSection title="Résiliation">
      <p>
        Vous pouvez demander la fermeture de votre compte à tout moment. L'éditeur peut suspendre ou fermer un compte en
        cas d'usage abusif, frauduleux ou illégal du service.
      </p>
    </GoupixDexLegalSection>

    <GoupixDexLegalSection title="Évolution des conditions">
      <p>
        Ces conditions peuvent évoluer avec le service. La date de la dernière mise à jour figure en haut de cette page.
      </p>
    </GoupixDexLegalSection>

    <GoupixDexLegalSection title="Droit applicable">
      <p>Les présentes conditions sont régies par le droit français.</p>
    </GoupixDexLegalSection>
  </GoupixDexLegalDocument>
</template>

<script lang="ts" setup>
import { PUBLISHER } from '~/utils/publisher'

definePageMeta({
  layout: 'landing',
})

useGoupixPageSeo(
  "Conditions d'utilisation",
  "Conditions d'utilisation de GoupixDex : accès au service, compte, annonces sur les plateformes, prix et responsabilité.",
)
</script>
