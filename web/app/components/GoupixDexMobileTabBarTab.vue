<template>
  <ULink
    :to="props.to"
    :aria-current="props.to && props.isActive ? 'page' : undefined"
    raw
    class="flex min-w-0 flex-1 items-center justify-center transition [-webkit-tap-highlight-color:transparent] active:opacity-60"
    :class="props.isActive ? 'text-(--app-accent)' : 'text-(--app-ink-soft)'"
  >
    <UIcon :name="props.icon" class="size-6" />
  </ULink>
</template>

<script lang="ts" setup>
import type { GoupixDexMobileTabBarTabProps } from '~/types/GoupixDexMobileTabBarTab'

const props: GoupixDexMobileTabBarTabProps = defineProps({
  icon: {
    type: String,
    required: true,
  },
  isActive: {
    type: Boolean,
    required: true,
  },
  to: {
    type: String,
    default: undefined,
  },
})
</script>
