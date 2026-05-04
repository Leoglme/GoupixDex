// @ts-check
import eslintConfigPrettier from 'eslint-config-prettier'
import eslintPluginJSDoc from 'eslint-plugin-jsdoc'
import eslintPluginPrettier from 'eslint-plugin-prettier'
import eslintPluginUnusedImports from 'eslint-plugin-unused-imports'
import eslintPluginTypeScript from '@typescript-eslint/eslint-plugin'
import withNuxt from './.nuxt/eslint.config.mjs'

export default withNuxt(
  {
    name: 'goupixdex/ignores',
    ignores: ['dist', '.output', 'node_modules', '.nuxt', 'src-tauri/target', 'coverage', '*.min.js'],
  },
  eslintPluginJSDoc.configs['flat/recommended'],
  {
    plugins: {
      'unused-imports': eslintPluginUnusedImports,
      prettier: eslintPluginPrettier,
      '@typescript-eslint': eslintPluginTypeScript,
    },
    rules: {
      '@typescript-eslint/no-explicit-any': 'error',
      /**
       * Signatures are enforced by TypeScript / `vue-tsc`. Requiring `: ReturnType` on every
       * `function`/`async function` adds noise without meaningful safety gains.
       */
      '@typescript-eslint/explicit-function-return-type': 'off',
      /**
       * Explicit typing for refs/computed/props follows `vue-tsc` and team conventions
       * (`CONTEXT/CODE_STANDARDS.md`). The ESLint `typedef` rule duplicated ~1000+ redundant
       * annotations on locals — disabled in favor of the TS checker.
       */
      '@typescript-eslint/typedef': 'off',
      '@typescript-eslint/no-unused-vars': 'off',
      'unused-imports/no-unused-imports': 'error',
      'unused-imports/no-unused-vars': [
        'error',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
        },
      ],
      'vue/no-multiple-template-root': 'off',
      'vue/component-name-in-template-casing': ['error', 'PascalCase', { registeredComponentsOnly: false }],
      'vue/block-order': [
        'error',
        {
          order: ['template', 'script', 'style'],
        },
      ],
      'prettier/prettier': 'error',
      'jsdoc/require-jsdoc': [
        'error',
        {
          require: {
            FunctionDeclaration: true,
            MethodDefinition: true,
            ArrowFunctionExpression: false,
            FunctionExpression: true,
          },
        },
      ],
    },
  },
  {
    files: ['**/*.vue'],
    settings: {
      jsdoc: {
        mode: 'typescript',
      },
    },
    rules: {
      // Vue SFC: TypeScript + vue-tsc documentent les signatures ; pas de JSDoc obligatoire sur les fonctions.
      'jsdoc/require-jsdoc': 'off',
      'jsdoc/require-param': 'off',
      'jsdoc/require-returns': 'off',
      'jsdoc/require-param-description': 'off',
      'jsdoc/require-returns-description': 'off',
      // Param/return types are enforced by TypeScript; JSDoc describes behavior (English).
      'jsdoc/require-param-type': 'off',
      'jsdoc/require-returns-type': 'off',
      // TS covers return types; skip `: void` on every watch/onMounted arrow callback.
      '@typescript-eslint/explicit-function-return-type': 'off',
      // Explicit Ref<T>/ComputedRef<T> per CODE_STANDARDS — enforced by review + vue-tsc; full ESLint typedef was ~650 noisy locals per .vue.
      '@typescript-eslint/typedef': 'off',
    },
  },
  {
    files: ['app/composables/**/*.ts'],
    settings: {
      jsdoc: {
        mode: 'typescript',
      },
    },
    rules: {
      /**
       * Match Vue SFC policy: English prose + `@param` / `@returns`, types from TypeScript.
       * `eslint-plugin-jsdoc` “recommended” is stricter on `.ts` than we want for composables.
       */
      'jsdoc/require-param-type': 'off',
      'jsdoc/require-returns-type': 'off',
      'jsdoc/require-param-description': 'off',
      'jsdoc/require-returns-description': 'error',
      'jsdoc/tag-lines': 'off',
      'jsdoc/check-param-names': 'off',
      /**
       * TS signatures already document shapes; `typescript` mode otherwise insists on one JSDoc
       * `@param` per object property (`payload.sold_price`, `opts.quiet`, …).
       */
      'jsdoc/require-param': 'off',
    },
  },
  {
    files: ['app/utils/**/*.ts', 'scripts/**/*.mjs'],
    rules: {
      // Utilitaires et scripts Node : signatures décrites par TypeScript ; pas de JSDoc strict obligatoire.
      'jsdoc/require-jsdoc': 'off',
      'jsdoc/require-param': 'off',
      'jsdoc/require-returns': 'off',
      'jsdoc/require-param-description': 'off',
      'jsdoc/require-returns-description': 'off',
      'jsdoc/require-param-type': 'off',
      'jsdoc/require-returns-type': 'off',
    },
  },
  eslintConfigPrettier,
)
