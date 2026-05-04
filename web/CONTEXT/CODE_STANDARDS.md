# 🧹 Code Standards & Architecture — GoupixDex (web)

> This file is the **single source of truth** for code quality, tooling, and architecture conventions.
> Cursor must read and strictly follow every rule defined here before writing any code.
> When in doubt about a package version or API, **always check the official documentation online** — do not rely on training data which may be outdated.

This document is aligned with the PrePeers B2B frontend standards (`integrations/prepeers-front-b2b`) and is **strictly enforced** for `web/`.

**GoupixDex rule additions (NON-NEGOTIABLE):**

- Every component filename must start with **`GoupixDex`** (e.g. `GoupixDexArticleCard.vue`).
- Every component usage in templates must use **PascalCase** and the **`GoupixDex`** prefix.
- All TypeScript rules below apply everywhere: every `ref`, `computed`, prop, and function must be explicitly typed.
- No `interface` / `type` definitions inside `.vue` files: put them in `app/types/` and import them.
- In `.vue` files, block order is **`<template>` first**, then `<script lang="ts" setup>` (and **no `<style>`**).

---

## 📦 Stack & Versions

Always install the **latest stable version** of each package. Before installing, check:

- Nuxt → https://nuxt.com
- Vue → https://vuejs.org
- TypeScript → https://www.typescriptlang.org
- TailwindCSS → https://tailwindcss.com
- @nuxtjs/i18n → https://i18n.nuxtjs.org
- @nuxtjs/sitemap → https://nuxtseo.com/sitemap
- @nuxtjs/robots → https://nuxtseo.com/robots
- @tailwindcss/vite → https://tailwindcss.com/docs/installation/vite
- ESLint → https://eslint.org
- Prettier → https://prettier.io
- Husky → https://typicode.github.io/husky
- commitlint → https://commitlint.js.org
- vue-tsc → https://github.com/vuejs/language-tools

**Minimum baseline (always install latest above these):**

| Package           | Min version |
| ----------------- | ----------- |
| nuxt              | 4.x         |
| vue               | 3.5.x       |
| typescript        | 5.x         |
| tailwindcss       | 4.x         |
| @tailwindcss/vite | 4.x         |
| @nuxtjs/i18n      | 10.x        |
| eslint            | 9.x         |
| prettier          | 3.x         |
| husky             | 9.x         |
| vue-tsc           | 3.x         |

---

## 🏗️ Project Architecture

The project follows the **Nuxt 4 `app/` directory convention**. All application source lives under `app/`.

```
web/
├── app/
│   ├── assets/
│   │   └── css/
│   │       └── main.css          # Tailwind directives only — no custom CSS here
│   ├── components/
│   │   ├── articles/, amazon/, auth/, …   # Feature folders + shared UI
│   ├── composables/              # useXxx() composables — typed, no any
│   ├── layouts/                  # Nuxt layouts (default.vue, landing.vue…)
│   ├── pages/                    # Nuxt file-based routing
│   ├── plugins/                  # Nuxt plugins (client/server)
│   ├── services/                 # API call wrappers, business logic (no Vue reactivity here)
│   ├── types/                    # Shared TypeScript interfaces & types
│   │   ├── api.types.ts
│   │   ├── school.types.ts
│   │   └── …
│   └── utils/                    # Pure utility functions (no Vue, no Nuxt)
├── public/                       # Static assets
├── server/                       # Nitro server routes (if needed)
├── src-tauri/                    # Tauri desktop shell (Windows/macOS)
├── .husky/
│   └── pre-commit
├── .env.example
├── .gitignore
├── .prettierignore
├── commitlint.json
├── eslint.config.js
├── nuxt.config.ts
├── package.json
├── prettier.config.js
└── tsconfig.json
```

### Folder responsibilities

**`components/<domain>/`** — Feature-specific UI (e.g. `articles/`, `amazon/`, `auth/`).
Keep atoms reusable; heavy logic stays in composables.

**`composables/`** — Vue 3 composables using `ref`, `computed`, `watch` (fully typed).
Examples: `useArticles.ts`, `useAuth.ts`, `useDashboard.ts`

**`server/`** (optional) — Nitro API routes under `server/` when used.

**`types/`** — TypeScript `interface` and `type` definitions only. No logic.

**`utils/`** — Pure functions. No side effects. No Vue. Fully unit-testable.
Examples: `formatDate.ts`, `slugify.ts`, `groupBy.ts`

---

## 🔷 TypeScript — Ultra Strict

### Rules — NON-NEGOTIABLE

- `any` is **FORBIDDEN**. Zero tolerance. Use `unknown` and narrow, or define a proper type.
- Every `const` holding a primitive or object literal must be **explicitly annotated** (do not rely on inference for “constants”): `const pageSize: number = 20`
- Every `ref()` must carry its reactive type on the **binding** using `Ref<T>` imported from `vue`. **Do not** repeat the same generic on `ref` — that duplicates the type (redundant cast).
  - `const count: Ref<number> = ref(0)` ✅
  - `const count: Ref<number> = ref<number>(0)` ❌ **FORBIDDEN** (redundant `ref<T>` when `Ref<T>` is already on the left-hand side)
- Every `computed()` must be explicitly typed on the binding using `ComputedRef<T>` imported from `vue`:
  - `const isReady: ComputedRef<boolean> = computed(() => …)`
  - Do **not** use `computed<T>(() => …)` as the _only_ typing mechanism — the `const` binding must be `ComputedRef<T>`.
- `watch` / `watchEffect` callbacks must type their parameters and return `void` when applicable:
  - `watch(isOpen, (open: boolean): void => { … })`
- Vue lifecycle hooks must type their callbacks:
  - `onMounted((): void => { … })`
  - `onBeforeUnmount((): void => { … })`
- Every function parameter must be typed: `function foo(id: number, name: string): void`
- Every function return type must be explicitly declared
- Every reactive variable, prop, emit, and inject must be typed
- Use `interface` for objects that can be extended, `type` for unions and primitives
- No implicit `any` from missing type annotations — if TS infers `any`, add the type

### tsconfig.json

```json
{
  "files": [],
  "references": [
    { "path": "./.nuxt/tsconfig.app.json" },
    { "path": "./.nuxt/tsconfig.server.json" },
    { "path": "./.nuxt/tsconfig.shared.json" },
    { "path": "./.nuxt/tsconfig.node.json" }
  ]
}
```

> Nuxt 4 manages strict mode internally via `.nuxt/tsconfig.app.json` (sets `"strict": true`).
> Do NOT override it — extend it if needed in `nuxt.config.ts` via `typescript.tsConfig`.
> Run `npm run lint:ts` (vue-tsc --noEmit) to validate types before committing.

### Examples

```ts
// ✅ CORRECT
import type { ComputedRef, Ref } from 'vue'

const pageSize: number = 20
const count: Ref<number> = ref(0)
const schools: Ref<School[]> = ref([])
const isLoading: ComputedRef<boolean> = computed(() => schools.value.length === 0)

function fetchSchool(id: number): Promise<School> {
  return schoolService.getById(id)
}

// ❌ FORBIDDEN
const count = ref(0) // implicit number — add explicit Ref<number> on the binding
const doubled: Ref<number> = ref<number>(0) // redundant ref<T> — use ref(0)
const data = ref<any>(null) // any is forbidden
function doSomething(x) {} // missing parameter type
```

---

## 🎨 Styling — TailwindCSS Only

- Use **only TailwindCSS utility classes** for all styling
- **`<style>` blocks are FORBIDDEN** in Vue components — not even `<style scoped>`
- **No inline `style` attributes** unless driven by dynamic values that Tailwind cannot express (e.g. CSS custom properties for dynamic colors)
- **Prefer Tailwind’s design-scale utilities** (`mt-7`, `w-full`, `max-w-7xl`, `gap-6`, `text-xl`, …) over arbitrary values (`mt-[27px]`, `w-[663.5px]`, …).
  - Arbitrary values are allowed when the maquette requires **pixel-perfect** positioning, but if a close scale match exists, choose the scale utility.
- Use `class:` directive or ternary in `:class` binding for conditional classes
- Responsive design: use Tailwind's responsive prefixes (`sm:`, `md:`, `lg:`, `xl:`)
- Follow the design tokens from the maquette (orange, yellow-light, white, blue/purple)

```vue
<!-- ✅ CORRECT -->
<button class="rounded-lg bg-orange-500 px-6 py-3 font-semibold text-white transition-colors hover:bg-orange-600">
  Get started
</button>

<!-- ❌ FORBIDDEN -->
<button style="background: orange; padding: 12px">Get started</button>
<style scoped>
button {
  background: orange;
}
</style>
```

---

## 💬 Comments & JSDoc

- **All code comments must be written in English** — no French comments in source files
- Above every function or method (including composable functions, service methods, and utils), add a **JSDoc block in English**
- JSDoc must include `@param`, `@returns`, and `@throws` where applicable
- Inline comments inside a function body are allowed but must stay in English

```ts
import type { ComputedRef } from 'vue'

/**
 * Fetches a school by its unique identifier.
 * @param id - The unique identifier of the school.
 * @returns A promise resolving to the school data.
 * @throws Will throw if the network request fails.
 */
async function fetchSchoolById(id: number): Promise<School> {
  return await schoolService.getById(id)
}

/**
 * Returns true if the user has completed onboarding.
 * @returns Whether onboarding is complete.
 */
const hasCompletedOnboarding: ComputedRef<boolean> = computed(() => {
  // Check both profile and preferences to determine completion
  return user.value?.profile !== null && user.value?.preferences !== null
})
```

---

## 🌍 Internationalisation (i18n)

- Use `@nuxtjs/i18n` latest version
- Supported locales: **FR** (default), **EN**, **ES**
- Locale files: `i18n/locales/fr.json`, `en.json`, `es.json`
- Strategy: `prefix_except_default` (FR has no prefix, EN → `/en/`, ES → `/es/`)
- **Never hardcode user-facing strings** in components — always use `$t('key')` or `useI18n().t('key')`
- **Prefer `$t('key')` directly in templates** over introducing `const { t } = useI18n()` solely for template usage.
  - Keep `useI18n()` only when the script needs translations (computed strings, validators, `useHead`, etc.).
- Translation keys must be **namespaced** by section: `hero.title`, `features.cta`, `pricing.perMonth`

```vue
<!-- ✅ CORRECT -->
<h1>{{ $t('hero.title') }}</h1>

<!-- ❌ FORBIDDEN -->
<h1>Trouvez vos futurs étudiants</h1>
```

---

## 🔍 SEO

- Use `@nuxtjs/sitemap` and `@nuxtjs/robots`
- Use `useHead()` or `useSeoMeta()` in every page to define meta tags
- Every page must define: `title`, `description`, `og:title`, `og:description`, `og:image`
- Sitemap and robots must exclude private/admin routes if any
- SSR must be enabled (`ssr: true` in `nuxt.config.ts`)

---

## 🔧 Tooling Configuration

### ESLint — `eslint.config.js`

Inspired from `dibodev.fr-frontend`. Must include:

- `@typescript-eslint` (strict)
- `eslint-plugin-vue`
- `eslint-plugin-jsdoc` (enforce JSDoc above functions)
- `eslint-plugin-unused-imports` (no unused imports or variables)
- `eslint-plugin-prettier` (run prettier as an ESLint rule)
- `eslint-config-prettier` (disable conflicting rules)
- Rule: `@typescript-eslint/no-explicit-any: error` (any is a hard error)
- Rule: `@typescript-eslint/explicit-function-return-type: error`
- Rule: `@typescript-eslint/no-unused-vars: error`
- Rule: `vue/component-name-in-template-casing: ['error', 'PascalCase']`

### Prettier — `prettier.config.js`

```js
export default {
  semi: false,
  singleQuote: true,
  trailingComma: 'all',
  printWidth: 120,
  tabWidth: 2,
  plugins: ['prettier-plugin-tailwindcss'],
}
```

### commitlint — `commitlint.json`

```json
{
  "extends": ["@commitlint/config-conventional"],
  "rules": {
    "type-enum": [
      2,
      "always",
      ["feat", "fix", "ci", "docs", "style", "refactor", "test", "chore", "perf", "revert", "build"]
    ]
  }
}
```

### Husky pre-commit — `web/.husky/pre-commit`

```sh
npm run lint
```

The `lint` script must run sequentially:

1. `prettier --check .`
2. `eslint .`
3. `vue-tsc --noEmit`

All three must pass before a commit is accepted.

**Monorepo:** in GoupixDex, `.git` is at the repo root and hooks live under `web/.husky`. The `prepare` script in `web/package.json` runs `scripts/git-hooks-path.mjs`, which executes `git config core.hooksPath web/.husky` from the repository root (no `npx husky` required). Run `npm install` from `web/` once per clone so hooks are wired.

### package.json scripts

```json
{
  "scripts": {
    "dev": "nuxt dev",
    "build": "nuxt build",
    "generate": "nuxt generate",
    "preview": "nuxt preview",
    "postinstall": "nuxt prepare",
    "lint:prettier": "prettier --check .",
    "lint:prettier:fix": "prettier --write .",
    "lint:eslint": "eslint .",
    "lint:eslint:fix": "eslint . --fix",
    "lint:ts": "vue-tsc --noEmit",
    "lint": "npm run lint:prettier && npm run lint:eslint && npm run lint:ts",
    "lint:fix": "npm run lint:prettier:fix && npm run lint:eslint:fix"
  }
}
```

---

## 🧱 Vue Component Conventions

### Single-File Component block order — NON-NEGOTIABLE

Every `.vue` file **must** declare its blocks in the following order:

1. `<template>` at the **top**
2. `<script lang="ts" setup>` at the **bottom** (right under the closing `</template>`)
3. **Prefer no `<style>` block** — use Tailwind / Nuxt UI; legacy scoped `<style>` should shrink over time.

```vue
<!-- ✅ CORRECT -->
<template>
  <button :class="baseClass">{{ props.label }}</button>
</template>

<script lang="ts" setup>
import type { ExampleButtonProps } from '~/types/ExampleButton'

/**
 * Define the ExampleButton props.
 */
const props: ExampleButtonProps = defineProps({
  label: { type: String, required: true },
})
</script>
```

```vue
<!-- ❌ FORBIDDEN — script before template -->
<script lang="ts" setup>
// ...
</script>

<template>
  <!-- ... -->
</template>
```

The `<script>` opening tag **must** use `lang="ts" setup` in this exact order.

### Internal `<script setup>` ordering

Inside the `<script lang="ts" setup>` block, follow this order:

1. imports (types first via `import type { … }`)
2. props (`defineProps`) & emits (`defineEmits`)
3. composables (`useI18n()`, `useRoute()`, custom composables…)
4. refs & reactive state (`const x: Ref<T> = ref(…)`, `reactive<T>(…)` — no redundant `ref<T>`)
5. computed (`const x: ComputedRef<T> = computed(() => …)`)
6. methods/functions (each preceded by a JSDoc block in English)
7. watchers (`watch`, `watchEffect`) — callbacks fully typed
8. lifecycle hooks (`onMounted`, `onBeforeUnmount`…) — callbacks fully typed

**Readability / grouping rules (NON-NEGOTIABLE):**

- Group related declarations together (all refs together, all computeds together, all functions together).
- Avoid duplicated lifecycle hooks when a single hook can cleanly handle teardown (merge `onBeforeUnmount` blocks).

### Component naming (GoupixDex)

- File name: **PascalCase** matching the component (`ArticleForm.vue`, `BrandHeader.vue`).
- Usage in template: **PascalCase** → `<ArticleForm />`, `<BrandHeader />`.
- With `pathPrefix: false`, nested folders do not prefix names — keep filenames unique enough to avoid collisions (e.g. `articles/ArticleForm.vue`).

### Props — typed with a runtime `defineProps({…})` + imported interface — NON-NEGOTIABLE

Every component declares its props using **the runtime API** of `defineProps`, paired with a **dedicated `interface` exported from `app/types/`**. This pattern is mandatory because it enforces explicit `default` values, Vue's runtime validation, and a single shared type per component.

**1) Declare the props interface in `app/types/<ComponentName>.ts`** (one file per component, named after the component):

```ts
// app/types/ExampleButton.ts

/**
 * Visual variant of the ExampleButton.
 */
export type ExampleButtonVariant = 'dark' | 'outline' | 'ghost'

/**
 * Size of the ExampleButton.
 */
export type ExampleButtonSize = 'sm' | 'md'

/**
 * Props for the ExampleButton component.
 */
export interface ExampleButtonProps {
  label: string
  to?: string
  variant?: ExampleButtonVariant
  size?: ExampleButtonSize
}
```

**2) Use the runtime `defineProps({…})` and apply the type to the returned variable:**

```vue
<script lang="ts" setup>
import type { PropType } from 'vue'
import type { ExampleButtonProps, ExampleButtonSize, ExampleButtonVariant } from '~/types/ExampleButton'

/**
 * Define the ExampleButton props.
 */
const props: ExampleButtonProps = defineProps({
  label: {
    type: String,
    required: true,
  },
  to: {
    type: String,
    default: undefined,
  },
  variant: {
    type: String as PropType<ExampleButtonVariant>,
    default: 'outline',
  },
  size: {
    type: String as PropType<ExampleButtonSize>,
    default: 'md',
  },
})
</script>
```

Rules:

- The `interface` lives in `app/types/<ComponentName>.ts` and is `export`ed.
- The interface name follows the pattern `<ComponentName>Props`.
- Use `as PropType<…>` for union/string-literal/object props so Vue keeps the narrow type at runtime.
- Every optional prop **must** declare a `default` value (use `default: undefined` for nullable optionals).
- Every required prop **must** declare `required: true`.
- A JSDoc block in English **must** precede the `defineProps` call.
- **`withDefaults(defineProps<…>())` is FORBIDDEN**. Defaults must live in the runtime `defineProps({ … })` object (see example above).

```ts
// ❌ FORBIDDEN — generic-only defineProps without runtime validation/defaults
const props = defineProps<Props>()

// ❌ FORBIDDEN — inline interface, missing imported type
const props = defineProps({ label: { type: String, required: true } })

// ❌ FORBIDDEN — withDefaults + generic props
const props = withDefaults(defineProps<Props>(), { variant: 'blue' })
```

### Emits — always typed with `defineEmits<{}>()`

```ts
const emit = defineEmits<{
  (e: 'submit', value: string): void
  (e: 'close'): void
}>()
```

### No Options API

Use **Composition API with `<script setup>`** exclusively. Options API is forbidden.

---

## 📝 Conventional Commits

Every commit must follow the Conventional Commits specification:

```
<type>(<scope>): <short description>

Types: feat | fix | ci | docs | style | refactor | test | chore | perf | revert | build
```

Examples:

```
feat(landing): add hero section with i18n support
fix(seo): correct og:image meta tag on landing page
chore(deps): upgrade nuxt to latest version
refactor(composables): extract useSchools logic into dedicated composable
```

---

## 🚫 Hard Rules Summary

| Rule                                                          | Status                               |
| ------------------------------------------------------------- | ------------------------------------ |
| `any` type                                                    | ❌ FORBIDDEN                         |
| `<style>` blocks in components                                | ⚠️ Avoid for new code; legacy exists |
| Hardcoded user-facing strings                                 | ⚠️ Prefer i18n keys for new strings  |
| Options API                                                   | ❌ FORBIDDEN                         |
| French comments in source code                                | ❌ FORBIDDEN                         |
| Untyped refs, computed, props                                 | ❌ FORBIDDEN                         |
| Redundant `ref<T>(…)` when the binding is already `Ref<T>`    | ❌ FORBIDDEN                         |
| `withDefaults(defineProps<…>())`                              | ❌ FORBIDDEN                         |
| Inline styles (non-dynamic)                                   | ❌ FORBIDDEN                         |
| Committing without passing lint                               | ❌ FORBIDDEN                         |
| `<script>` placed before `<template>` in `.vue` files         | ❌ FORBIDDEN                         |
| Generic-only `defineProps<Props>()` (no runtime defaults)     | ❌ FORBIDDEN                         |
| JSDoc above every function                                    | ✅ REQUIRED                          |
| Explicit return types                                         | ✅ REQUIRED                          |
| English-only comments                                         | ✅ REQUIRED                          |
| TailwindCSS for all styling                                   | ✅ REQUIRED                          |
| Conventional commits                                          | ✅ REQUIRED                          |
| `<template>` first, `<script lang="ts" setup>` last in `.vue` | ✅ REQUIRED                          |
| Props interface exported from `app/types/<ComponentName>.ts`  | ✅ REQUIRED                          |

---

## 🔗 Reference Repo

For config file inspiration (eslint.config.js, prettier.config.js, husky, commitlint, nuxt.config.ts, tsconfig.json, folder structure), refer to:

**https://github.com/Leoglme/dibodev.fr-frontend**

The folder `dibodev.fr-frontend/` is accessible at the root of the workspace and can be read directly.
