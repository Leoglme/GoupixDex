<template>
  <div class="ring-default bg-default overflow-hidden rounded-xl ring-1">
    <button
      type="button"
      class="group flex w-full cursor-pointer items-start gap-3 px-3 py-3 text-left select-none sm:px-4 sm:py-4"
      :aria-expanded="open"
      @click="open = !open"
    >
      <div class="min-w-0 flex-1 space-y-0.5">
        <p class="text-highlighted text-sm font-medium">{{ title }}</p>
        <p v-if="description" class="text-muted text-xs leading-snug">{{ description }}</p>
      </div>
      <div class="flex shrink-0 items-center gap-2 pt-0.5">
        <slot name="trailing" />
        <UIcon
          name="i-lucide-chevron-down"
          class="text-muted group-hover:text-highlighted size-4 shrink-0 transition-transform duration-300 ease-out motion-reduce:transition-none"
          :class="open ? 'rotate-180' : ''"
        />
      </div>
    </button>

    <div
      class="grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none"
      :class="open ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'"
    >
      <div class="overflow-hidden">
        <div class="border-default border-t" :class="bodyUi">
          <slot />
        </div>
        <div v-if="$slots.footer" class="border-default border-t" :class="footerUi ?? 'p-4 sm:p-5'">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string
    description?: string
    bodyUi?: string
    footerUi?: string
  }>(),
  {
    description: undefined,
    bodyUi: 'p-0',
    footerUi: undefined,
  },
)

const open = defineModel<boolean>('open', { default: true })
</script>
