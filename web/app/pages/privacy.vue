<script setup lang="ts">
definePageMeta({
  layout: 'auth'
})

useGoupixPageSeo(
  'Politique de confidentialité',
  'Politique de confidentialité de GoupixDex : données collectées, usage, conservation et contact Dibodev.'
)
</script>

<template>
  <div class="min-h-dvh bg-default text-default">
    <section class="relative overflow-hidden border-b border-default/40 px-5 pt-32 pb-20 sm:px-8 sm:pt-40 sm:pb-24 lg:pt-48 lg:pb-28">
      <div class="pointer-events-none absolute -top-24 left-1/2 h-80 w-80 -translate-x-1/2 rounded-full bg-primary/[0.10] blur-3xl" />
      <div class="pointer-events-none absolute -bottom-16 right-0 h-72 w-72 rounded-full bg-primary/[0.06] blur-3xl" />

      <div class="relative mx-auto w-full max-w-4xl space-y-4 text-left">
        <span class="inline-flex items-center rounded-full bg-primary/10 px-4 py-1.5 text-xs font-semibold tracking-wide text-primary ring-1 ring-primary/20">
          Confidentialité
        </span>
        <h1 class="text-3xl font-bold tracking-tight text-highlighted sm:text-4xl">
          Politique de confidentialité — GoupixDex
        </h1>
        <p class="max-w-3xl text-sm leading-relaxed text-muted sm:text-base">
          Cette politique décrit comment les données sont traitées sur GoupixDex. Le service est développé par
          <strong class="text-highlighted">Dibodev</strong>.
        </p>
        <p class="text-sm text-muted">
          Dernière mise à jour : 17 avril 2026
        </p>
      </div>
    </section>

    <main class="mx-auto flex w-full max-w-5xl justify-center px-5 py-14 sm:px-8 sm:py-20">
      <UCard class="w-full max-w-4xl ring-1 ring-default/60 shadow-sm">
        <div class="space-y-8 text-sm leading-7 text-toned sm:text-base">
          <section class="space-y-2">
            <h2 class="text-xl font-semibold text-highlighted">
              1. Responsable du traitement
            </h2>
            <p>
              GoupixDex est développé par Dibodev. Pour toute question liée à la confidentialité et aux données
              personnelles, vous pouvez écrire à
              <a href="mailto:contact@dibodev.fr" class="text-primary underline underline-offset-2">
                contact@dibodev.fr
              </a>.
            </p>
          </section>

          <section class="space-y-2">
            <h2 class="text-xl font-semibold text-highlighted">
              2. Données traitées
            </h2>
            <p>
              Nous pouvons traiter des données de compte (email, mot de passe chiffré), des données d'inventaire
              (articles, photos, prix), des paramètres de publication (Vinted / eBay) et des jetons OAuth
              nécessaires à la connexion aux services tiers.
            </p>
          </section>

          <section class="space-y-2">
            <h2 class="text-xl font-semibold text-highlighted">
              3. Finalités
            </h2>
            <p>
              Ces données sont utilisées pour authentifier les utilisateurs, gérer l'inventaire, proposer des
              suggestions de prix, publier des annonces sur les marketplaces activées et assurer le support technique.
            </p>
          </section>

          <section class="space-y-2">
            <h2 class="text-xl font-semibold text-highlighted">
              4. Conservation et sécurité
            </h2>
            <p>
              Les données sont conservées pendant l'utilisation du compte, puis supprimées dans un délai raisonnable
              après demande, sauf obligation légale contraire. Des mesures techniques de sécurité sont appliquées
              (contrôles d'accès, chiffrement des secrets sensibles, supervision).
            </p>
          </section>

          <section class="space-y-2">
            <h2 class="text-xl font-semibold text-highlighted">
              5. Vos droits
            </h2>
            <p>
              Vous pouvez demander l'accès, la rectification ou la suppression de vos données, ainsi que la limitation
              de certains traitements, selon la réglementation applicable.
            </p>
          </section>

          <section class="space-y-2">
            <h2 class="text-xl font-semibold text-highlighted">
              6. Contact
            </h2>
            <p>
              Pour toute question : 
              <a href="mailto:contact@dibodev.fr" class="text-primary underline underline-offset-2">
                contact@dibodev.fr
              </a>
            </p>
          </section>
        </div>
      </UCard>
    </main>
  </div>
</template>
