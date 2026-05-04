<template>
  <UDashboardPanel id="downloads">
    <template #header>
      <UDashboardNavbar title="Télécharger l'application">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="mx-auto w-full max-w-7xl space-y-8 px-4 py-6 sm:px-8 sm:py-10">
        <div
          class="border-default from-primary/10 via-elevated/50 to-primary/5 relative overflow-hidden rounded-2xl border bg-gradient-to-br p-8 sm:p-10"
        >
          <div class="bg-primary/10 pointer-events-none absolute -top-16 -right-16 size-64 rounded-full blur-3xl" />
          <div class="bg-primary/5 pointer-events-none absolute -bottom-20 -left-12 size-56 rounded-full blur-3xl" />
          <div class="relative flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div class="max-w-2xl space-y-3">
              <p class="text-primary text-sm font-medium">Application desktop GoupixDex</p>
              <h1 class="text-highlighted text-2xl font-semibold tracking-tight sm:text-3xl">
                Installez l'app sur votre ordinateur
              </h1>
              <p class="text-muted text-base leading-relaxed">
                Choisissez la ligne qui correspond à votre système : Windows ou macOS, puis le bon type de processeur.
                La publication Vinted n'est disponible que dans cette application — le site web sert à gérer le reste.
              </p>
            </div>
            <div class="flex shrink-0 gap-3 sm:flex-col sm:items-end">
              <div
                class="bg-elevated/80 border-default flex items-center gap-2 rounded-xl border px-4 py-3 backdrop-blur-sm"
              >
                <UIcon name="i-simple-icons-windows" class="size-8 text-[#0078D4]" />
                <UIcon name="i-simple-icons-apple" class="text-highlighted size-8" />
              </div>
            </div>
          </div>
        </div>

        <UAlert
          color="info"
          variant="subtle"
          icon="i-lucide-sparkles"
          title="Quel fichier télécharger ?"
          description="Sous Windows, privilégiez l'installateur « recommandé ». Sur Mac récent (puce M), prenez la ligne Apple Silicon ; sur Mac Intel, la ligne Intel."
        />

        <UCard class="ring-default/60 shadow-sm ring-1" :ui="{ body: 'sm:p-8 p-6' }">
          <template #header>
            <div class="flex flex-wrap items-center justify-between gap-3 px-1">
              <div class="min-w-0 space-y-1">
                <p class="text-muted text-sm">Version disponible</p>
                <p class="text-highlighted text-lg font-semibold">
                  Téléchargements
                  <template v-if="releaseVersionLabel">
                    <span
                      class="text-primary mt-1 block font-mono text-base sm:mt-0 sm:inline sm:before:content-['\00a0—\00a0']"
                    >
                      {{ releaseVersionLabel }}
                    </span>
                  </template>
                </p>
                <p
                  v-if="release?.tag_name && release.name?.trim() && release.name.trim() !== release.tag_name"
                  class="text-muted text-sm"
                >
                  Étiquette Git : {{ release.tag_name }}
                </p>
              </div>
              <div v-if="release?.tag_name" class="flex shrink-0 flex-wrap items-center gap-2">
                <UBadge color="neutral" variant="subtle" size="md">
                  {{ release.tag_name }}
                </UBadge>
                <UBadge v-if="release.prerelease" color="warning" variant="subtle" size="md"> Préversion </UBadge>
              </div>
            </div>
          </template>

          <div v-if="pending" class="space-y-4 py-4">
            <p class="text-muted text-sm">Récupération des installateurs depuis GitHub…</p>
            <UProgress animation="carousel" />
          </div>

          <div v-else-if="error" class="space-y-4 py-2">
            <UAlert
              color="error"
              variant="subtle"
              icon="i-lucide-alert-circle"
              title="Impossible de récupérer les téléchargements"
              :description="String(error)"
            />
            <UButton color="neutral" variant="soft" icon="i-lucide-refresh-cw" @click="refresh()"> Réessayer </UButton>
          </div>

          <div v-else class="space-y-8">
            <p v-if="release?.published_at" class="text-muted text-sm">
              Publié le
              {{ new Date(release.published_at).toLocaleString('fr-FR', { dateStyle: 'long', timeStyle: 'short' }) }}
            </p>

            <div class="grid gap-8 lg:grid-cols-2 lg:gap-10">
              <!-- Windows -->
              <div class="space-y-4">
                <div class="border-default flex items-center gap-3 border-b pb-3">
                  <div class="flex size-12 items-center justify-center rounded-xl bg-[#0078D4]/15">
                    <UIcon name="i-simple-icons-windows" class="size-7 text-[#0078D4]" />
                  </div>
                  <div>
                    <h2 class="text-highlighted text-lg font-semibold">Windows</h2>
                    <p class="text-muted text-sm">PC sous Windows 10 ou 11 (64 bits)</p>
                  </div>
                </div>

                <div
                  v-if="!windowsDownloads.length"
                  class="border-default text-muted rounded-xl border border-dashed px-4 py-8 text-center text-sm"
                >
                  Aucun installateur Windows dans cette version pour le moment.
                </div>

                <div v-else class="space-y-4">
                  <UCard
                    v-for="item in windowsDownloads"
                    :key="item.id"
                    variant="subtle"
                    class="overflow-hidden transition-shadow hover:shadow-md"
                  >
                    <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                      <div class="flex min-w-0 gap-4">
                        <div class="flex size-10 shrink-0 items-center justify-center rounded-lg bg-[#0078D4]/10">
                          <UIcon :name="item.icon" class="size-5 text-[#0078D4]" />
                        </div>
                        <div class="min-w-0 space-y-1">
                          <p class="text-highlighted leading-snug font-medium">
                            {{ item.label }}
                          </p>
                          <p class="text-muted text-sm leading-relaxed">
                            {{ item.description }}
                          </p>
                          <p v-if="formatBytes(item.asset.size)" class="text-muted pt-1 text-xs">
                            Taille : {{ formatBytes(item.asset.size) }}
                          </p>
                        </div>
                      </div>
                      <UButton
                        :to="item.asset.browser_download_url"
                        target="_blank"
                        icon="i-lucide-download"
                        color="primary"
                        class="shrink-0 sm:self-center"
                      >
                        Télécharger
                      </UButton>
                    </div>
                  </UCard>
                </div>
              </div>

              <!-- macOS -->
              <div class="space-y-4">
                <div class="border-default flex items-center gap-3 border-b pb-3">
                  <div class="flex size-12 items-center justify-center rounded-xl bg-neutral-500/15">
                    <UIcon name="i-simple-icons-apple" class="text-highlighted size-7" />
                  </div>
                  <div>
                    <h2 class="text-highlighted text-lg font-semibold">macOS</h2>
                    <p class="text-muted text-sm">Mac avec Apple Silicon ou processeur Intel</p>
                  </div>
                </div>

                <div
                  v-if="!macDownloads.length"
                  class="border-default text-muted rounded-xl border border-dashed px-4 py-8 text-center text-sm"
                >
                  Aucun installateur macOS dans cette version pour le moment.
                </div>

                <div v-else class="space-y-4">
                  <UCard
                    v-for="item in macDownloads"
                    :key="item.id"
                    variant="subtle"
                    class="overflow-hidden transition-shadow hover:shadow-md"
                  >
                    <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                      <div class="flex min-w-0 gap-4">
                        <div class="flex size-10 shrink-0 items-center justify-center rounded-lg bg-neutral-500/10">
                          <UIcon :name="item.icon" class="text-highlighted size-5" />
                        </div>
                        <div class="min-w-0 space-y-1">
                          <p class="text-highlighted leading-snug font-medium">
                            {{ item.label }}
                          </p>
                          <p class="text-muted text-sm leading-relaxed">
                            {{ item.description }}
                          </p>
                          <p v-if="formatBytes(item.asset.size)" class="text-muted pt-1 text-xs">
                            Taille : {{ formatBytes(item.asset.size) }}
                          </p>
                        </div>
                      </div>
                      <UButton
                        :to="item.asset.browser_download_url"
                        target="_blank"
                        icon="i-lucide-download"
                        color="primary"
                        class="shrink-0 sm:self-center"
                      >
                        Télécharger
                      </UButton>
                    </div>
                  </UCard>
                </div>
              </div>
            </div>
          </div>
        </UCard>
      </div>
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  "Télécharger l'application",
  'Installez GoupixDex sur Windows ou macOS pour la publication Vinted et retrouvez le même tableau de bord que sur le web.',
)

type ReleaseAsset = {
  /** GitHub id (unique per asset) — used for deduplication */
  id?: number
  name: string
  browser_download_url: string
  size?: number
}

type GithubRelease = {
  tag_name: string
  html_url: string
  name?: string
  published_at?: string
  draft?: boolean
  prerelease?: boolean
  assets: ReleaseAsset[]
}

type DownloadItem = {
  id: string
  asset: ReleaseAsset
  label: string
  description: string
  platform: 'windows' | 'macos'
  kind: 'exe' | 'msi' | 'dmg' | 'app-archive'
  icon: string
  sortKey: number
}

const runtime = useRuntimeConfig()

const repoSlug = computed(() => (runtime.public.githubRepo as string | undefined)?.trim() || 'leogu/GoupixDex')
const releaseChannel = computed(() => (runtime.public.desktopReleaseChannel as string | undefined)?.trim() || 'latest')
const releasesBase = computed(
  () => (runtime.public.githubApiBase as string | undefined)?.trim() || 'https://api.github.com',
)

const {
  data: release,
  pending,
  error,
  refresh,
} = await useAsyncData(
  'desktop-github-release',
  async () => {
    const base = releasesBase.value
    const slug = repoSlug.value
    const channel = releaseChannel.value

    if (channel === 'latest') {
      // Latest **stable** release (not draft, not prerelease) — single asset set
      try {
        return await $fetch<GithubRelease>(`${base}/repos/${slug}/releases/latest`)
      } catch (e: unknown) {
        const status =
          (e as { status?: number; statusCode?: number })?.status ?? (e as { statusCode?: number })?.statusCode
        if (status !== 404) {
          throw e
        }
        const rows = await $fetch<GithubRelease[]>(`${base}/repos/${slug}/releases`, {
          query: { per_page: '20' },
        })
        const picked = rows.find((r) => !r.draft && !r.prerelease) ?? rows.find((r) => !r.draft)
        if (!picked) {
          throw new Error('No published release on this repository.')
        }
        return picked
      }
    }

    return await $fetch<GithubRelease>(`${base}/repos/${slug}/releases/tags/${encodeURIComponent(channel)}`)
  },
  { watch: [releasesBase, repoSlug, releaseChannel] },
)

/**
 * GitHub should not return the same asset twice; filter by id / URL just in case.
 * @param assets - Raw release assets list
 * @returns {ReleaseAsset[]} De-duplicated assets
 */
function dedupeAssets(assets: ReleaseAsset[]): ReleaseAsset[] {
  const seen = new Set<string>()
  const out: ReleaseAsset[] = []
  for (const a of assets) {
    const key = a.id != null ? `id:${a.id}` : a.browser_download_url || a.name
    if (seen.has(key)) {
      continue
    }
    seen.add(key)
    out.push(a)
  }
  return out
}

/**
 * Map a GitHub release asset to a platform-specific download row (or skip unknown extensions).
 * @param asset - Release asset metadata from API
 * @returns {DownloadItem | null} Row config or null when unsupported
 */
function classifyAsset(asset: ReleaseAsset): DownloadItem | null {
  const n = asset.name

  if (/\.msi$/i.test(n)) {
    return {
      id: n,
      asset,
      platform: 'windows',
      kind: 'msi',
      icon: 'i-simple-icons-windows',
      sortKey: 20,
      label: 'Windows x64 — installateur MSI',
      description:
        "Format .msi : utile si votre entreprise impose ce type de paquet, ou si l'installateur .exe pose problème. Windows 10 ou 11 en 64 bits.",
    }
  }

  if (/\.exe$/i.test(n)) {
    const isSetup = /setup\.exe$/i.test(n) || /-setup\.exe$/i.test(n)
    return {
      id: n,
      asset,
      platform: 'windows',
      kind: 'exe',
      icon: 'i-simple-icons-windows',
      sortKey: isSetup ? 10 : 15,
      label: isSetup ? 'Windows x64 — installateur (recommandé)' : 'Windows x64 — installateur',
      description:
        'Le plus simple pour un PC récent : téléchargez, double-cliquez et suivez les étapes. Compatible Windows 10/11 en 64 bits.',
    }
  }

  if (/\.dmg$/i.test(n)) {
    const appleSilicon = /aarch64|arm64/i.test(n)
    return {
      id: n,
      asset,
      platform: 'macos',
      kind: 'dmg',
      icon: 'i-simple-icons-apple',
      sortKey: appleSilicon ? 10 : 20,
      label: appleSilicon ? 'macOS — Apple Silicon (M1, M2, M3…)' : 'macOS — Mac Intel (x64)',
      description: appleSilicon
        ? 'Pour les Mac avec puce Apple (M1 et suivantes). Ouvrez le fichier .dmg, puis faites glisser GoupixDex dans le dossier Applications.'
        : "Pour les Mac à processeur Intel. Ouvrez le .dmg, puis glissez l'application dans Applications.",
    }
  }

  if (/\.app\.tar\.gz$/i.test(n)) {
    const appleSilicon = /aarch64|arm64/i.test(n)
    return {
      id: n,
      asset,
      platform: 'macos',
      kind: 'app-archive',
      icon: 'i-simple-icons-apple',
      sortKey: appleSilicon ? 30 : 40,
      label: appleSilicon ? 'macOS — archive .app (Apple Silicon)' : 'macOS — archive .app (Intel)',
      description:
        "Réservé aux utilisateurs à l'aise avec le terminal : décompressez l'archive pour obtenir l'app sans passer par un .dmg.",
    }
  }

  return null
}

/**
 * Stable UI ordering for mixed installers (Windows/macOS).
 * @param items - Parsed download rows
 * @returns {DownloadItem[]} Sorted copy
 */
function sortItems(items: DownloadItem[]): DownloadItem[] {
  return [...items].sort((a, b) => a.sortKey - b.sortKey || a.label.localeCompare(b.label))
}

/**
 * Multiple release assets can share the same label (e.g. two “setup” .exe files): keep one,
 * preferring the larger file (full installer vs secondary artifact).
 * @param items - Parsed download rows (same platform)
 * @returns {DownloadItem[]} De-duplicated rows sorted for display
 */
function dedupeDownloadItemsByLabel(items: DownloadItem[]): DownloadItem[] {
  const byLabel = new Map<string, DownloadItem>()
  for (const item of items) {
    const prev = byLabel.get(item.label)
    if (!prev) {
      byLabel.set(item.label, item)
      continue
    }
    const ps = prev.asset.size ?? 0
    const ns = item.asset.size ?? 0
    if (ns > ps) {
      byLabel.set(item.label, item)
    }
  }
  return sortItems([...byLabel.values()])
}

const windowsDownloads = computed(() => {
  const items = dedupeAssets(release.value?.assets ?? [])
    .map(classifyAsset)
    .filter((x): x is DownloadItem => Boolean(x && x.platform === 'windows'))
  return dedupeDownloadItemsByLabel(items)
})

const macDownloads = computed(() => {
  const items = dedupeAssets(release.value?.assets ?? [])
    .map(classifyAsset)
    .filter((x): x is DownloadItem => Boolean(x && x.platform === 'macos'))
  return dedupeDownloadItemsByLabel(items)
})

const releaseVersionLabel = computed(() => {
  const r = release.value
  if (!r) {
    return ''
  }
  if (r.name?.trim()) {
    return r.name.trim()
  }
  return r.tag_name ?? ''
})

/**
 * Compact human-readable file size for asset subtitles.
 * @param n - Byte length from GitHub API
 * @returns {string} Label like `12.4 MB`, or empty when unknown
 */
function formatBytes(n?: number): string {
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
