<template>
  <UCard
    :ui="{
      root: 'group overflow-hidden ring-1 ring-default transition hover:ring-primary/35 hover:shadow-md hover:shadow-black/15',
      body: 'p-3 sm:p-3',
    }"
  >
    <div class="flex flex-col items-stretch gap-2 lg:flex-row lg:gap-2">
      <!-- Image + lien Amazon (lien en haut à droite tant que la carte est en colonne) -->
      <div
        class="flex w-full min-w-0 items-start justify-between gap-2 lg:w-[6.75rem] lg:max-w-[6.75rem] lg:shrink-0 lg:justify-center"
      >
        <div
          class="relative flex min-w-0 flex-1 justify-start bg-transparent max-lg:min-h-[8rem] lg:min-h-0 lg:w-full lg:flex-none lg:justify-center"
        >
          <img
            v-if="invite.image_url"
            :src="invite.image_url"
            :alt="invite.title"
            class="max-h-36 w-full object-contain object-left 2xl:max-h-30 2xl:w-max"
            loading="lazy"
          />
          <div
            v-else
            class="bg-muted/40 flex min-h-20 w-full items-center justify-start rounded-md px-1.5 lg:min-h-[5.5rem] lg:justify-center"
          >
            <UIcon name="i-lucide-image-off" class="text-dimmed size-8" />
          </div>
        </div>
        <UButton
          v-if="productLink"
          :to="productLink"
          target="_blank"
          rel="noopener noreferrer"
          size="xs"
          variant="link"
          trailing-icon="i-lucide-external-link"
          class="shrink-0 self-start !px-0 pt-0.5 max-lg:inline-flex lg:hidden"
        >
          {{ amazonLinkLabel }}
        </UButton>
      </div>

      <div class="min-w-0 flex-1 space-y-1 self-start px-1.5 pt-0 sm:px-2 lg:self-center">
        <p class="text-highlighted line-clamp-2 text-sm leading-snug font-medium">
          {{ invite.title }}
        </p>
        <p v-if="invite.asin" class="text-dimmed font-mono text-xs">
          {{ invite.asin }}
        </p>
        <div class="flex flex-wrap gap-1.5">
          <UBadge v-if="invite.price_hint" color="neutral" variant="subtle" size="sm">
            {{ invite.price_hint }}
          </UBadge>
          <UBadge :color="statusColor" :variant="statusBadgeVariant" size="sm">
            {{ statusLabel }}
          </UBadge>
        </div>

        <div
          v-if="productLink && canShowRequestCta"
          class="mt-3 flex flex-col flex-wrap gap-2 sm:mt-4 lg:flex-row lg:items-center lg:justify-between"
        >
          <UButton
            color="primary"
            variant="solid"
            size="xs"
            icon="i-lucide-send"
            class="w-fit"
            :loading="requestInviteLoading"
            :disabled="requestInviteLoading"
            @click="emit('request-invite', invite)"
          >
            Demander l’invitation
          </UButton>
          <UButton
            :to="productLink"
            target="_blank"
            rel="noopener noreferrer"
            size="xs"
            variant="link"
            trailing-icon="i-lucide-external-link"
            class="hidden !px-0 lg:inline-flex"
          >
            {{ amazonLinkLabel }}
          </UButton>
        </div>
        <div v-else-if="productLink" class="mt-3 hidden lg:block">
          <UButton
            :to="productLink"
            target="_blank"
            rel="noopener noreferrer"
            size="xs"
            variant="link"
            trailing-icon="i-lucide-external-link"
            class="!px-0"
            :color="invite.status === 'expired' ? 'neutral' : 'primary'"
          >
            {{ amazonLinkLabel }}
          </UButton>
        </div>
      </div>
    </div>
  </UCard>
</template>

<script setup lang="ts">
import type { ComputedRef, PropType } from 'vue'
import type {
  GoupixDexAmazonInviteCardProps,
  GoupixDexAmazonInviteStatusBadgeColor,
} from '~/types/GoupixDexAmazonInviteCard'
import type { AmazonInvite, AmazonInviteStatus } from '~/types/amazonInvites'

const props: GoupixDexAmazonInviteCardProps = defineProps({
  invite: {
    type: Object as PropType<AmazonInvite>,
    required: true,
  },
  requestInviteLoading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits<{
  'request-invite': [invite: AmazonInvite]
}>()

const productLink: ComputedRef<string | null> = computed(() => {
  const inv = props.invite
  const u = inv.product_url?.trim()
  if (u) {
    return u
  }
  const a = inv.asin?.trim()
  if (a) {
    return `https://www.amazon.fr/dp/${a}`
  }
  return null
})

const amazonLinkLabel: ComputedRef<string> = computed(() => {
  return props.invite.status === 'accepted' ? 'Voir l’offre sur Amazon' : 'Voir sur Amazon'
})

const statusLabel: ComputedRef<string> = computed(() => {
  const s: AmazonInviteStatus = props.invite.status
  const m: Record<AmazonInviteStatus, string> = {
    accepted: 'Commandable',
    requested: 'Invitation demandée',
    not_requested: 'Non demandée',
    listing_only: 'Sur invitation',
    expired: 'Invitation expirée',
    unknown: 'Statut indéterminé',
  }
  return m[s] ?? s
})

const statusColor: ComputedRef<GoupixDexAmazonInviteStatusBadgeColor> = computed(() => {
  const s: AmazonInviteStatus = props.invite.status
  const m: Record<AmazonInviteStatus, GoupixDexAmazonInviteStatusBadgeColor> = {
    accepted: 'success',
    requested: 'warning',
    not_requested: 'neutral',
    listing_only: 'primary',
    expired: 'neutral',
    unknown: 'neutral',
  }
  return m[s] ?? 'neutral'
})

const statusBadgeVariant: ComputedRef<'subtle' | 'outline'> = computed(() => {
  return props.invite.status === 'listing_only' ? 'outline' : 'subtle'
})

const canShowRequestCta: ComputedRef<boolean> = computed(() => {
  if (!productLink.value) {
    return false
  }
  return props.invite.status === 'not_requested'
})
</script>
