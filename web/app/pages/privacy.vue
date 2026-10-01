<template>
  <GoupixDexLegalDocument
    document-id="privacy"
    title="Politique de confidentialité"
    intro="Ce que GoupixDex collecte, pourquoi, combien de temps, et comment exercer vos droits."
  >
    <GoupixDexLegalSection title="Responsable du traitement">
      <p>
        {{ PUBLISHER.fullName }}, entrepreneur individuel (Dibodev), {{ PUBLISHER.address }}. Pour toute question sur
        vos données : <a :href="PUBLISHER.emailHref" class="landing-link">{{ PUBLISHER.email }}</a
        >.
      </p>
    </GoupixDexLegalSection>

    <GoupixDexLegalSection title="Données collectées">
      <ul class="grid gap-2">
        <GoupixDexLegalListItem term="Compte :">
          adresse e-mail, mot de passe (stocké haché), nom et téléphone si vous les renseignez, message de votre demande
          d'accès.
        </GoupixDexLegalListItem>
        <GoupixDexLegalListItem term="Stock et ventes :">
          cartes, articles, photos, prix d'achat et de vente, commandes Cardmarket importées, produits scellés et
          classeurs que vous créez.
        </GoupixDexLegalListItem>
        <GoupixDexLegalListItem term="Expédition :">
          votre adresse d'expéditeur. L'adresse d'un acheteur eBay est lue chez eBay au moment d'imprimer son étiquette,
          sans être conservée.
        </GoupixDexLegalListItem>
        <GoupixDexLegalListItem term="Plateformes connectées :">
          vos identifiants Vinted et Amazon et votre autorisation eBay, chiffrés sur le serveur. Ils servent uniquement
          aux actions que vous lancez.
        </GoupixDexLegalListItem>
        <GoupixDexLegalListItem term="Formulaire de contact :">
          nom, e-mail, téléphone si vous le donnez, et votre message.
        </GoupixDexLegalListItem>
        <GoupixDexLegalListItem term="Données techniques :">
          adresse IP et journaux du serveur, pour la sécurité du service.
        </GoupixDexLegalListItem>
      </ul>
    </GoupixDexLegalSection>

    <GoupixDexLegalSection title="Application desktop">
      <p>
        L'application pour Windows et macOS pilote votre propre navigateur (Chrome ou Edge), sur votre ordinateur, pour
        Vinted, Leboncoin, Cardmarket et Amazon. Vos sessions de connexion à ces sites restent dans ce navigateur.
      </p>
    </GoupixDexLegalSection>

    <GoupixDexLegalSection title="Mesure d'audience">
      <p>
        GoupixDex mesure son audience avec Umami, sans cookie : aucune donnée n'identifie un visiteur ni ne le suit d'un
        site à l'autre, et les statistiques restent internes.
      </p>
    </GoupixDexLegalSection>

    <GoupixDexLegalSection title="Finalités et bases légales">
      <ul class="grid gap-2">
        <GoupixDexLegalListItem term="Exécution du contrat :">
          gérer votre compte, votre stock, vos annonces, vos ventes et votre collection.
        </GoupixDexLegalListItem>
        <GoupixDexLegalListItem term="Intérêt légitime :">
          répondre à vos messages, sécuriser le service et mesurer son audience sans cookie.
        </GoupixDexLegalListItem>
      </ul>
      <p>Vos données ne sont ni vendues, ni louées, ni utilisées à des fins publicitaires.</p>
    </GoupixDexLegalSection>

    <GoupixDexLegalSection title="Destinataires">
      <p>
        Seul l'éditeur accède à vos données. Des prestataires techniques les traitent pour son compte, chacun pour sa
        tâche :
      </p>
      <ul class="grid gap-2">
        <GoupixDexLegalListItem term="Hébergement :">OVH, en France.</GoupixDexLegalListItem>
        <GoupixDexLegalListItem term="Stockage des photos :">Supabase.</GoupixDexLegalListItem>
        <GoupixDexLegalListItem term="Publication sur eBay :">
          eBay reçoit les annonces que vous y publiez, avec l'autorisation que vous lui avez donnée.
        </GoupixDexLegalListItem>
        <GoupixDexLegalListItem term="Reconnaissance des cartes :">
          Groq reçoit la photo d'une carte quand la reconnaissance faite sur votre appareil ne suffit pas.
        </GoupixDexLegalListItem>
        <GoupixDexLegalListItem term="Envoi des e-mails :">Resend.</GoupixDexLegalListItem>
      </ul>
      <p>
        Quand un prestataire est établi hors de l'Union européenne, le transfert est encadré par les clauses
        contractuelles types de la Commission européenne.
      </p>
    </GoupixDexLegalSection>

    <GoupixDexLegalSection title="Durée de conservation">
      <ul class="grid gap-2">
        <GoupixDexLegalListItem term="Compte, stock et ventes :">
          tant que le compte est actif, puis suppression à sa fermeture ou sur simple demande.
        </GoupixDexLegalListItem>
        <GoupixDexLegalListItem term="Identifiants des plateformes :">
          supprimés dès que vous retirez la plateforme de vos réglages, ou avec votre compte.
        </GoupixDexLegalListItem>
        <GoupixDexLegalListItem term="Messages du formulaire :">3 ans après le dernier échange.</GoupixDexLegalListItem>
      </ul>
    </GoupixDexLegalSection>

    <GoupixDexLegalSection title="Vos droits">
      <p>
        Vous pouvez accéder à vos données, les corriger, les supprimer, les récupérer dans un format lisible, vous
        opposer à leur traitement ou en limiter l'usage. Écrivez à
        <a :href="PUBLISHER.emailHref" class="landing-link">{{ PUBLISHER.email }}</a> ou passez par la
        <NuxtLink to="/contact" class="landing-link">page contact</NuxtLink>&nbsp;: vous recevez une réponse sous un
        mois.
      </p>
      <p>Si vous estimez que vos droits ne sont pas respectés, vous pouvez saisir la CNIL sur cnil.fr.</p>
    </GoupixDexLegalSection>

    <GoupixDexLegalSection title="Cookies">
      <p>
        GoupixDex ne dépose aucun cookie de mesure d'audience ni de publicité. Votre session de connexion et vos
        préférences d'affichage restent dans le stockage local de votre navigateur, sans être transmises à un tiers. La
        déconnexion efface la session.
      </p>
    </GoupixDexLegalSection>
  </GoupixDexLegalDocument>
</template>

<script lang="ts" setup>
import { PUBLISHER } from '~/utils/publisher'

definePageMeta({
  layout: 'landing',
})

useGoupixPageSeo(
  'Politique de confidentialité',
  'Données collectées par GoupixDex, usage, durée de conservation, prestataires et exercice de vos droits.',
)
</script>
