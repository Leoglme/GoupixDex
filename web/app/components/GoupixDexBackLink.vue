<template>
  <a
    :href="fallbackHref"
    class="inline-flex w-fit items-center gap-1 text-sm font-medium text-(--app-accent) underline-offset-4 transition hover:text-(--app-accent) hover:underline"
    @click="goBack"
  >
    <UIcon name="i-lucide-arrow-left" class="size-4 shrink-0" aria-hidden />
    {{ props.label }}
  </a>
</template>

<script lang="ts" setup>
import type { ComputedRef } from 'vue'
import type { Router } from 'vue-router'
import type { GoupixDexBackLinkProps } from '~/types/GoupixDexBackLink'

/**
 * `to` = page parente, utilisée seulement quand la page a été ouverte sans historique (lien direct, nouvel onglet).
 */
const props: GoupixDexBackLinkProps = defineProps({
  to: {
    type: String,
    required: true,
  },
  label: {
    type: String,
    default: 'Retour',
  },
})

const router: Router = useRouter()

const fallbackHref: ComputedRef<string> = computed((): string => router.resolve(props.to).href)

/**
 * Revient à la page précédente de l'app, sinon à la page parente ; les clics modifiés gardent le lien natif.
 * @param event - Clic sur le lien.
 * @returns {void}
 */
function goBack(event: MouseEvent): void {
  if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
    return
  }
  event.preventDefault()
  if (typeof router.options.history.state.back === 'string') {
    router.back()
    return
  }
  navigateTo(props.to)
}
</script>
