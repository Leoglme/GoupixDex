<script setup lang="ts">
definePageMeta({ middleware: 'auth' })

type ReleaseAsset = {
  name: string
  browser_download_url: string
  size?: number
}

type GithubRelease = {
  tag_name: string
  html_url: string
  name?: string
  published_at?: string
  assets: ReleaseAsset[]
}

const runtime = useRuntimeConfig()

const repoSlug = computed(
  () => (runtime.public.githubRepo as string | undefined)?.trim() || 'leogu/GoupixDex'
)
const releaseChannel = computed(
  () => (runtime.public.desktopReleaseChannel as string | undefined)?.trim() || 'latest'
)
const releasesBase = computed(
  () => (runtime.public.githubApiBase as string | undefined)?.trim() || 'https://api.github.com'
)

const releaseApiUrl = computed(() => {
  if (releaseChannel.value === 'latest') {
    return `${releasesBase.value}/repos/${repoSlug.value}/releases/latest`
  }
  return `${releasesBase.value}/repos/${repoSlug.value}/releases/tags/${encodeURIComponent(releaseChannel.value)}`
})

const {
  data: release,
  pending,
  error,
  refresh
} = await useFetch<GithubRelease>(releaseApiUrl, { key: 'desktop-release' })

const windowsAssets = computed(() =>
  (release.value?.assets ?? []).filter(a => /\.(msi|exe)$/i.test(a.name))
)
const macAssets = computed(() =>
  (release.value?.assets ?? []).filter(a => /\.(dmg|pkg|app\.tar\.gz|zip)$/i.test(a.name))
)

function formatBytes(n?: number) {
  if (!n || n <= 0) {
    return ''
  }
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let val = n
  while (val >= 1024 && i < units.length - 1) {
    val /= 1024
    i++
  }
  return `${val.toFixed(val >= 10 || i === 0 ? 0 : 1)} ${units[i]}`
}
</script>

<template>
  <UDashboardPanel id="downloads">
    <template #header>
      <UDashboardNavbar title="Télécharger l’application desktop">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="p-4 sm:p-6 max-w-4xl space-y-6">
        <UAlert
          color="info"
          variant="subtle"
          icon="i-lucide-monitor-smartphone"
          title="La publication Vinted est disponible dans l’application desktop"
          description="Le web reste disponible pour la gestion quotidienne, mais la mise en ligne Vinted est réservée à l’app Windows/macOS."
        />

        <UCard>
          <template #header>
            <div class="flex flex-wrap items-center justify-between gap-2">
              <p class="font-medium text-highlighted">
                Dernière version
              </p>
              <UBadge v-if="release?.tag_name" color="neutral" variant="subtle">
                {{ release.tag_name }}
              </UBadge>
            </div>
          </template>

          <div v-if="pending" class="space-y-3">
            <p class="text-sm text-muted">
              Chargement des binaires depuis GitHub Releases…
            </p>
            <UProgress animation="carousel" />
          </div>

          <div v-else-if="error" class="space-y-3">
            <UAlert
              color="error"
              variant="subtle"
              icon="i-lucide-alert-circle"
              title="Impossible de récupérer les téléchargements"
              :description="String(error)"
            />
            <UButton color="neutral" variant="subtle" icon="i-lucide-refresh-cw" @click="refresh()">
              Réessayer
            </UButton>
          </div>

          <div v-else class="space-y-6">
            <div v-if="release?.published_at" class="text-xs text-muted">
              Publié le {{ new Date(release.published_at).toLocaleString('fr-FR') }}
            </div>

            <div class="grid gap-4 md:grid-cols-2">
              <UCard>
                <template #header>
                  <p class="font-medium text-highlighted">
                    Windows
                  </p>
                </template>
                <div class="space-y-2">
                  <p v-if="!windowsAssets.length" class="text-sm text-muted">
                    Aucun installateur Windows trouvé dans cette release.
                  </p>
                  <UButton
                    v-for="asset in windowsAssets"
                    :key="asset.name"
                    :to="asset.browser_download_url"
                    target="_blank"
                    icon="i-lucide-download"
                    class="w-full justify-between"
                    color="neutral"
                    variant="outline"
                  >
                    <span class="truncate">{{ asset.name }}</span>
                    <span class="text-xs text-muted">{{ formatBytes(asset.size) }}</span>
                  </UButton>
                </div>
              </UCard>

              <UCard>
                <template #header>
                  <p class="font-medium text-highlighted">
                    macOS
                  </p>
                </template>
                <div class="space-y-2">
                  <p v-if="!macAssets.length" class="text-sm text-muted">
                    Aucun installateur macOS trouvé dans cette release.
                  </p>
                  <UButton
                    v-for="asset in macAssets"
                    :key="asset.name"
                    :to="asset.browser_download_url"
                    target="_blank"
                    icon="i-lucide-download"
                    class="w-full justify-between"
                    color="neutral"
                    variant="outline"
                  >
                    <span class="truncate">{{ asset.name }}</span>
                    <span class="text-xs text-muted">{{ formatBytes(asset.size) }}</span>
                  </UButton>
                </div>
              </UCard>
            </div>

            <UButton
              v-if="release?.html_url"
              :to="release.html_url"
              target="_blank"
              color="neutral"
              variant="ghost"
              icon="i-lucide-github"
            >
              Voir la release complète sur GitHub
            </UButton>
          </div>
        </UCard>
      </div>
    </template>
  </UDashboardPanel>
</template>
