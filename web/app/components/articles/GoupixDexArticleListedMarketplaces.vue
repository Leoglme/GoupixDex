<template>
  <div class="inline-flex items-center justify-center gap-1.5" :title="tooltip" :aria-label="tooltip">
    <template v-for="icon in marketplaceIcons" :key="icon.marketplace">
      <a
        v-if="icon.listingUrl"
        :href="icon.listingUrl"
        target="_blank"
        rel="noopener noreferrer"
        :title="`Ouvrir l'annonce ${MARKETPLACE_NAMES[icon.marketplace]}`"
        :aria-label="`Ouvrir l'annonce ${MARKETPLACE_NAMES[icon.marketplace]}`"
        class="rounded-md transition-opacity hover:opacity-80"
      >
        <GoupixDexMarketplaceAppIcon :marketplace="icon.marketplace" />
      </a>
      <GoupixDexMarketplaceAppIcon v-else :marketplace="icon.marketplace" :is-greyed-out="!icon.isPublished" />
    </template>
  </div>
</template>

<script lang="ts" setup>
import type { ComputedRef, PropType } from 'vue'
import type {
  GoupixDexArticleListedMarketplacesProps,
  ListedMarketplaceIcon,
} from '~/types/GoupixDexArticleListedMarketplaces'
import type { ArticleMarketplaceListings, Marketplace } from '~/types/Marketplace'
import { MARKETPLACE_NAMES, MARKETPLACES, marketplaceListingUrl } from '~/utils/marketplaces'

const props: GoupixDexArticleListedMarketplacesProps = defineProps({
  row: {
    type: Object as PropType<ArticleMarketplaceListings>,
    required: true,
  },
  showVinted: {
    type: Boolean,
    default: true,
  },
  showEbay: {
    type: Boolean,
    default: true,
  },
  showLeboncoin: {
    type: Boolean,
    default: true,
  },
  hasListingLinks: {
    type: Boolean,
    default: false,
  },
})

const marketplaceIcons: ComputedRef<ListedMarketplaceIcon[]> = computed((): ListedMarketplaceIcon[] => {
  const isShown: Record<Marketplace, boolean> = {
    vinted: Boolean(props.showVinted),
    ebay: Boolean(props.showEbay),
    leboncoin: Boolean(props.showLeboncoin),
  }
  const isPublished: Record<Marketplace, boolean> = {
    vinted: Boolean(props.row.published_on_vinted),
    ebay: Boolean(props.row.published_on_ebay),
    leboncoin: Boolean(props.row.published_on_leboncoin),
  }
  return MARKETPLACES.filter((marketplace: Marketplace): boolean => isShown[marketplace]).map(
    (marketplace: Marketplace): ListedMarketplaceIcon => ({
      marketplace,
      isPublished: isPublished[marketplace],
      listingUrl: props.hasListingLinks ? marketplaceListingUrl(props.row, marketplace) : null,
    }),
  )
})

const tooltip: ComputedRef<string> = computed((): string =>
  marketplaceIcons.value
    .map(
      (icon: ListedMarketplaceIcon): string =>
        `${MARKETPLACE_NAMES[icon.marketplace]} : ${icon.isPublished ? 'en ligne' : 'non publié'}`,
    )
    .join(' · '),
)
</script>
