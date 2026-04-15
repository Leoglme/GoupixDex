// https://nuxt.com/docs/api/configuration/nuxt-config
const isDesktopBuild = process.env.NUXT_DESKTOP_BUILD === '1'

export default defineNuxtConfig({
  ssr: !isDesktopBuild,
  modules: [
    '@nuxt/eslint',
    '@nuxt/ui',
    '@vueuse/nuxt'
  ],

  // Noms de composants = nom de fichier (ex. LoginForm, ArticleCard), sans préfixe de dossier
  components: [
    {
      path: '~/components',
      pathPrefix: false
    }
  ],

  devtools: {
    enabled: !isDesktopBuild
  },

  css: ['~/assets/css/main.css'],

  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || 'http://127.0.0.1:8000',
      /** Worker Python local (Vinted / nodriver) — app Tauri uniquement */
      vintedLocalBase:
        process.env.NUXT_PUBLIC_VINTED_LOCAL_BASE || 'http://127.0.0.1:18766',
      githubRepo: process.env.NUXT_PUBLIC_GITHUB_REPO || 'leogu/GoupixDex',
      desktopReleaseChannel: process.env.NUXT_PUBLIC_DESKTOP_RELEASE_CHANNEL || 'latest',
      githubApiBase: process.env.NUXT_PUBLIC_GITHUB_API_BASE || 'https://api.github.com'
    }
  },

  routeRules: {
    '/api/**': {
      cors: true
    },
    '/settings/members': { redirect: '/settings/users' }
  },

  nitro: isDesktopBuild
    ? {
        preset: 'static'
      }
    : undefined,

  compatibilityDate: '2024-07-11',

  eslint: {
    config: {
      stylistic: {
        commaDangle: 'never',
        braceStyle: '1tbs'
      }
    }
  }
})
