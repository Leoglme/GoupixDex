// https://nuxt.com/docs/api/configuration/nuxt-config
const isDesktopBuild = process.env.NUXT_DESKTOP_BUILD === '1'

export default defineNuxtConfig({
  modules: ['@nuxt/eslint', '@nuxt/ui', '@vueuse/nuxt', '@nuxtjs/sitemap', '@nuxtjs/robots'],
  ssr: !isDesktopBuild,

  // Component names = file name (e.g. LoginForm, ArticleCard), no folder prefix
  components: [
    {
      path: '~/components',
      pathPrefix: false,
    },
  ],

  devtools: {
    enabled: !isDesktopBuild,
  },

  app: {
    head: {
      script: [
        ...(process.env.NODE_ENV === 'production'
          ? [
              {
                src: 'https://www.umami.dibodev.fr/script.js',
                defer: true,
                'data-website-id': 'dcb5d16e-a263-480d-add7-261c6c6c9397',
              },
            ]
          : []),
      ],
    },
  },

  css: ['~/assets/css/main.css'],

  site: {
    url: process.env.NUXT_PUBLIC_SITE_URL || 'https://goupixdex.dibodev.fr',
    name: 'GoupixDex',
  },

  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || 'http://127.0.0.1:8000',
      /** Local Python worker (Vinted / nodriver) — Tauri app only */
      vintedLocalBase: process.env.NUXT_PUBLIC_VINTED_LOCAL_BASE || 'http://127.0.0.1:18766',
      /** Local Python worker (Amazon invites / nodriver) — mainly desktop app */
      amazonLocalBase: process.env.NUXT_PUBLIC_AMAZON_LOCAL_BASE || 'http://127.0.0.1:18768',
      siteUrl: process.env.NUXT_PUBLIC_SITE_URL || 'https://goupixdex.dibodev.fr',
      githubRepo: process.env.NUXT_PUBLIC_GITHUB_REPO || 'leogu/GoupixDex',
      desktopReleaseChannel: process.env.NUXT_PUBLIC_DESKTOP_RELEASE_CHANNEL || 'latest',
      githubApiBase: process.env.NUXT_PUBLIC_GITHUB_API_BASE || 'https://api.github.com',
    },
  },

  routeRules: {
    '/api/**': {
      cors: true,
    },
    '/settings/members': { redirect: '/users' },
    '/settings/users': { redirect: '/users' },
    '/settings/users/create': { redirect: '/users' },
    '/dashboard': { headers: { 'X-Robots-Tag': 'noindex, nofollow' } },
    '/downloads': { headers: { 'X-Robots-Tag': 'noindex, nofollow' } },
    '/articles/**': { headers: { 'X-Robots-Tag': 'noindex, nofollow' } },
    '/settings/**': { headers: { 'X-Robots-Tag': 'noindex, nofollow' } },
    '/users': { headers: { 'X-Robots-Tag': 'noindex, nofollow' } },
    '/amazon-invites': { headers: { 'X-Robots-Tag': 'noindex, nofollow' } },
    '/setup-password/**': { headers: { 'X-Robots-Tag': 'noindex, nofollow' } },
    '/login': { headers: { 'X-Robots-Tag': 'noindex, nofollow' } },
  },

  compatibilityDate: '2024-07-11',

  nitro: isDesktopBuild
    ? {
        preset: 'static',
      }
    : undefined,

  eslint: {
    config: {
      stylistic: {
        commaDangle: 'never',
        braceStyle: '1tbs',
      },
    },
  },

  /**
   * App desktop / `nuxt generate` : sans SSR, Nuxt Icon utilise le provider `iconify` côté client.
   * `clientBundle.scan` embarque les icônes détectées dans les `.vue` (via `@iconify-json/*` local)
   * pour éviter chargements partiels / courses au premier rendu.
   */
  icon: {
    clientBundle: {
      scan: true,
      sizeLimitKb: 1024,
    },
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
          '/amazon-invites',
          '/setup-password/**',
          '/login',
        ],
      },
    ],
    sitemap: ['/sitemap.xml'],
  },

  /**
   * Manual sitemap: do not use includeAppSources (all `pages/` routes),
   * or internal or demo routes get indexed.
   * Add only marketing / public URLs you want crawled.
   */
  sitemap: {
    sitemaps: false,
    includeAppSources: false,
    urls: ['/', '/request'],
  },
})
