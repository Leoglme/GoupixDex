// https://nuxt.com/docs/api/configuration/nuxt-config
const isDesktopBuild = process.env.NUXT_DESKTOP_BUILD === '1'

export default defineNuxtConfig({
  ssr: !isDesktopBuild,
  modules: [
    '@nuxt/eslint',
    '@nuxt/ui',
    '@vueuse/nuxt',
    '@nuxtjs/sitemap',
    '@nuxtjs/robots'
  ],

  app: {
    head: {
      script: [
        ...(process.env.NODE_ENV === 'production'
          ? [
              {
                src: 'https://www.umami.dibodev.fr/script.js',
                defer: true,
                'data-website-id': 'dcb5d16e-a263-480d-add7-261c6c6c9397'
              }
            ]
          : [])
      ]
    }
  },

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
      siteUrl: process.env.NUXT_PUBLIC_SITE_URL || 'https://goupixdex.dibodev.fr',
      githubRepo: process.env.NUXT_PUBLIC_GITHUB_REPO || 'leogu/GoupixDex',
      desktopReleaseChannel: process.env.NUXT_PUBLIC_DESKTOP_RELEASE_CHANNEL || 'latest',
      githubApiBase: process.env.NUXT_PUBLIC_GITHUB_API_BASE || 'https://api.github.com'
    }
  },

  site: {
    url: process.env.NUXT_PUBLIC_SITE_URL || 'https://goupixdex.dibodev.fr',
    name: 'GoupixDex'
  },

  robots: {
    groups: [
      {
        userAgent: '*',
        allow: ['/'],
        disallow: [
          '/dashboard',
          '/downloads',
          '/articles',
          '/articles/**',
          '/settings',
          '/settings/**',
          '/users',
          '/setup-password/**',
          '/login'
        ]
      }
    ],
    sitemap: ['/sitemap.xml']
  },

  /**
   * Sitemap manuel : ne pas utiliser includeAppSources (toutes les routes pages/),
   * sinon des routes internes ou de démo se retrouvent indexées.
   * Ajouter ici uniquement les URLs marketing / publiques à faire crawler.
   */
  sitemap: {
    sitemaps: false,
    includeAppSources: false,
    urls: ['/', '/request']
  },

  routeRules: {
    '/api/**': {
      cors: true
    },
    '/settings/members': { redirect: '/users' },
    '/settings/users': { redirect: '/users' },
    '/settings/users/create': { redirect: '/users' },
    '/dashboard': { headers: { 'X-Robots-Tag': 'noindex, nofollow' } },
    '/downloads': { headers: { 'X-Robots-Tag': 'noindex, nofollow' } },
    '/articles/**': { headers: { 'X-Robots-Tag': 'noindex, nofollow' } },
    '/settings/**': { headers: { 'X-Robots-Tag': 'noindex, nofollow' } },
    '/users': { headers: { 'X-Robots-Tag': 'noindex, nofollow' } },
    '/setup-password/**': { headers: { 'X-Robots-Tag': 'noindex, nofollow' } },
    '/login': { headers: { 'X-Robots-Tag': 'noindex, nofollow' } }
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
