<template>
  <UFieldGroup class="w-full">
    <UButton
      color="primary"
      icon="i-lucide-send"
      class="h-11 min-w-0 flex-1 justify-center"
      :loading="isPublishing"
      :disabled="!marketplacesToPublish.length"
      @click="emit('publish', marketplacesToPublish)"
    >
      <span class="truncate">{{ publishEverywhereLabel }}</span>
      <template #trailing>
        <span class="flex shrink-0 items-center gap-1">
          <GoupixDexMarketplaceAppIcon
            v-for="marketplace in marketplacesToPublish"
            :key="marketplace"
            :marketplace="marketplace"
          />
        </span>
      </template>
    </UButton>
    <UDropdownMenu :items="publishMenuItems" :content="{ align: 'end' }">
      <UButton
        color="primary"
        icon="i-lucide-chevron-down"
        class="h-11 w-11 justify-center border-s border-black/15"
        aria-label="Publier sur une seule marketplace"
      />
      <template #item-leading="{ item }">
        <UIcon v-if="item.loading" name="i-lucide-loader-2" class="size-6 shrink-0 animate-spin" />
        <GoupixDexMarketplaceAppIcon v-else :marketplace="item.marketplace" />
      </template>
    </UDropdownMenu>
  </UFieldGroup>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType } from 'vue'
import type {
  GoupixDexPublishEverywhereButtonProps,
  MarketplacePublishMenuItem,
  MarketplacePublishOption,
} from '~/types/GoupixDexPublishEverywhereButton'
import type { Marketplace } from '~/types/Marketplace'
import { MARKETPLACE_NAMES } from '~/utils/marketplaces'

const props: GoupixDexPublishEverywhereButtonProps = defineProps({
  publishOptions: {
    type: Array as PropType<MarketplacePublishOption[]>,
    required: true,
  },
})

const emit = defineEmits<{
  publish: [marketplaces: Marketplace[]]
}>()

const marketplacesToPublish: ComputedRef<Marketplace[]> = computed((): Marketplace[] =>
  props.publishOptions
    .filter((option: MarketplacePublishOption): boolean => option.blockedReason === null && !option.isPublishing)
    .map((option: MarketplacePublishOption): Marketplace => option.marketplace),
)

const isPublishing: ComputedRef<boolean> = computed((): boolean =>
  props.publishOptions.some((option: MarketplacePublishOption): boolean => option.isPublishing),
)

const publishEverywhereLabel: ComputedRef<string> = computed((): string => {
  const [onlyMarketplace]: Marketplace[] = marketplacesToPublish.value
  return marketplacesToPublish.value.length === 1 && onlyMarketplace
    ? `Publier sur ${MARKETPLACE_NAMES[onlyMarketplace]}`
    : 'Publier partout'
})

const publishMenuItems: ComputedRef<MarketplacePublishMenuItem[]> = computed((): MarketplacePublishMenuItem[] =>
  props.publishOptions.map(
    (option: MarketplacePublishOption): MarketplacePublishMenuItem => ({
      marketplace: option.marketplace,
      label: `Publier sur ${MARKETPLACE_NAMES[option.marketplace]}`,
      description: option.blockedReason ?? undefined,
      disabled: option.blockedReason !== null || option.isPublishing,
      loading: option.isPublishing,
      onSelect: (): void => {
        emit('publish', [option.marketplace])
      },
    }),
  ),
)
</script>
