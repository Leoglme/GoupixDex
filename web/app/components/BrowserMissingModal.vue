<script setup lang="ts">
/**
 * Modale affichée au lancement de l'app desktop si aucun navigateur supporté
 * (Chrome ou Edge) n'est installé. Vinted (publication + synchro) en a besoin :
 * le worker local pilote ce navigateur via nodriver.
 *
 * Côté web (sans Tauri), `noBrowser` reste à `false` → la modale ne s'affiche jamais.
 */
const { isDesktopApp } = useDesktopRuntime()
const { state, checked, check, openExternal } = useBrowserAvailability()

const open = ref(false)

async function refresh() {
  await check(true)
  open.value = Boolean(state.value?.noBrowser)
}

onMounted(async () => {
  if (!isDesktopApp.value) {
    return
  }
  await check()
  open.value = Boolean(state.value?.noBrowser)
})

watch(
  () => state.value?.noBrowser,
  (v) => {
    if (checked.value) {
      open.value = Boolean(v)
    }
  }
)

async function installChrome() {
  await openExternal(state.value?.chromeInstallUrl || 'https://www.google.com/intl/fr_fr/chrome/')
}
</script>

<template>
  <UModal
    v-model:open="open"
    :dismissible="false"
    :close="false"
    title="Google Chrome est requis"
    :ui="{ content: 'max-w-lg' }"
  >
    <template #body>
      <div class="space-y-4">
        <p class="text-sm text-default">
          GoupixDex pilote <strong>Vinted</strong> (publication d'annonces et synchronisation
          de votre dressing) à travers <strong>Google&nbsp;Chrome</strong> installé sur votre
          machine. Microsoft&nbsp;Edge est utilisé comme solution de repli s'il est présent.
        </p>
        <p class="text-sm text-muted">
          Aucun de ces deux navigateurs n'a été détecté. Installez Chrome (gratuit, ~2&nbsp;min)
          puis cliquez sur « J'ai installé Chrome ».
        </p>

        <div class="rounded-md border border-default bg-elevated/50 p-3 text-xs text-muted space-y-1">
          <p>
            <span class="font-medium text-highlighted">Pourquoi&nbsp;?</span>
            Vinted bloque les requêtes serveur classiques (Cloudflare). GoupixDex contourne
            cela en automatisant un vrai navigateur installé chez vous, depuis votre IP
            résidentielle.
          </p>
        </div>
      </div>
    </template>

    <template #footer>
      <div class="flex w-full justify-end gap-2">
        <UButton
          color="neutral"
          variant="ghost"
          icon="i-lucide-refresh-cw"
          @click="refresh"
        >
          J'ai installé Chrome
        </UButton>
        <UButton
          icon="i-lucide-download"
          @click="installChrome"
        >
          Télécharger Chrome
        </UButton>
      </div>
    </template>
  </UModal>
</template>
