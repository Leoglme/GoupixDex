<template>
  <UDashboardPanel id="users">
    <template #header>
      <UDashboardNavbar title="Utilisateurs">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <UButton color="neutral" variant="ghost" icon="i-lucide-refresh-cw" :loading="loading" @click="load" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="space-y-4 p-4 sm:p-6">
        <UPageGrid class="gap-4 lg:grid-cols-3 lg:gap-px">
          <UPageCard
            icon="i-lucide-clock"
            title="Demandes en attente"
            variant="subtle"
            :ui="{
              leading: 'p-2.5 rounded-full bg-warning/10 ring ring-inset ring-warning/25 flex-col',
              title: 'font-normal text-muted text-xs uppercase',
            }"
            class="first:rounded-l-lg last:rounded-r-lg lg:rounded-none"
          >
            <p class="text-highlighted text-2xl font-semibold">
              {{ counts.pending }}
            </p>
          </UPageCard>
          <UPageCard
            icon="i-lucide-check-circle-2"
            title="Utilisateurs approuvés"
            variant="subtle"
            :ui="{
              leading: 'p-2.5 rounded-full bg-success/10 ring ring-inset ring-success/25 flex-col',
              title: 'font-normal text-muted text-xs uppercase',
            }"
            class="first:rounded-l-lg last:rounded-r-lg lg:rounded-none"
          >
            <p class="text-highlighted text-2xl font-semibold">
              {{ counts.approved }}
            </p>
          </UPageCard>
          <UPageCard
            icon="i-lucide-shield-off"
            title="Bannis"
            variant="subtle"
            :ui="{
              leading: 'p-2.5 rounded-full bg-error/10 ring ring-inset ring-error/25 flex-col',
              title: 'font-normal text-muted text-xs uppercase',
            }"
            class="first:rounded-l-lg last:rounded-r-lg lg:rounded-none"
          >
            <p class="text-highlighted text-2xl font-semibold">
              {{ counts.banned }}
            </p>
          </UPageCard>
        </UPageGrid>

        <div class="flex flex-wrap items-center justify-between gap-2">
          <UInput
            v-model="search"
            class="w-full max-w-sm"
            icon="i-lucide-search"
            placeholder="Rechercher par e-mail ou message…"
          />
          <USelect v-model="statusFilter" :items="statusItems" value-key="value" class="min-w-44" />
        </div>

        <UTable
          ref="tableRef"
          v-model:pagination="pagination"
          :pagination-options="{ getPaginationRowModel: getPaginationRowModel() }"
          :data="filteredUsers"
          :columns="columns"
          :loading="loading"
          class="shrink-0"
          :ui="{
            base: 'table-fixed border-separate border-spacing-0',
            thead: '[&>tr]:bg-elevated/50 [&>tr]:after:content-none',
            tbody: '[&>tr]:last:[&>td]:border-b-0',
            th: 'py-2 first:rounded-l-lg last:rounded-r-lg border-y border-default first:border-l last:border-r',
            td: 'border-b border-default',
            separator: 'h-0',
          }"
        />

        <div class="border-default flex items-center justify-between gap-3 border-t pt-4">
          <div class="text-muted text-sm">
            {{ filteredUsers.length }} utilisateur(s) affiché(s) sur {{ users.length }}.
          </div>
          <UPagination
            :default-page="(tableRef?.tableApi?.getState().pagination.pageIndex || 0) + 1"
            :items-per-page="tableRef?.tableApi?.getState().pagination.pageSize"
            :total="filteredUsers.length"
            @update:page="(p: number) => tableRef?.tableApi?.setPageIndex(p - 1)"
          />
        </div>
      </div>

      <GoupixDexUserPasswordLinkModal v-model="passwordLinkOpen" :user="passwordLinkUser" />
    </template>
  </UDashboardPanel>
</template>

<script setup lang="ts">
import type { ComputedRef, Ref } from 'vue'
import type { TableColumn } from '@nuxt/ui'
import type { Row } from '@tanstack/table-core'
import { getPaginationRowModel } from '@tanstack/table-core'
import type { AdminUser, UserStatus } from '~/composables/useUsers'

type AdminUserRowMenuItem = Record<string, unknown> | { type: 'separator' } | { type: 'label'; label: string }

definePageMeta({ middleware: 'admin' })

useGoupixPageSeo(
  'Utilisateurs',
  'Gérez les comptes GoupixDex : approbations, refus, bannissements et liens de mot de passe.',
)

const UButton = resolveComponent('UButton')
const UDropdownMenu = resolveComponent('UDropdownMenu')
const UserAvatar = resolveComponent('UserAvatar')
const UserStatusBadge = resolveComponent('UserStatusBadge')
const UBadge = resolveComponent('UBadge')

const toast = useToast()
const tableRef = useTemplateRef('tableRef')

const { listUsers, approveUser, rejectUser, banUser, deleteUser } = useUsers()

const users: Ref<AdminUser[]> = ref([])
const loading: Ref<boolean> = ref(true)
const search: Ref<string> = ref('')
const statusFilter: Ref<'all' | UserStatus> = ref('all')
const passwordLinkOpen: Ref<boolean> = ref(false)
const passwordLinkUser: Ref<{ id: number; email: string } | null> = ref(null)
const pagination: Ref<{ pageIndex: number; pageSize: number }> = ref({
  pageIndex: 0,
  pageSize: 10,
})

const eur: Intl.NumberFormat = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  maximumFractionDigits: 0,
})

async function load(): Promise<void> {
  loading.value = true
  try {
    users.value = await listUsers()
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  } finally {
    loading.value = false
  }
}

function replaceUser(updated: AdminUser): void {
  const idx = users.value.findIndex((u) => u.id === updated.id)
  if (idx >= 0) {
    users.value.splice(idx, 1, updated)
  }
}

async function withAction(label: string, fn: () => Promise<AdminUser>): Promise<void> {
  try {
    const u = await fn()
    replaceUser(u)
    toast.add({ title: label, color: 'success' })
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  }
}

async function onApprove(u: AdminUser): Promise<void> {
  await withAction(`${u.email} approuvé`, () => approveUser(u.id))
}

async function onReject(u: AdminUser): Promise<void> {
  await withAction(`Demande de ${u.email} refusée`, () => rejectUser(u.id))
}

async function onBan(u: AdminUser): Promise<void> {
  await withAction(`${u.email} banni`, () => banUser(u.id))
}

async function onDelete(u: AdminUser): Promise<void> {
  if (!confirm(`Supprimer définitivement ${u.email} ?`)) {
    return
  }
  try {
    await deleteUser(u.id)
    users.value = users.value.filter((x) => x.id !== u.id)
    toast.add({ title: 'Utilisateur supprimé', color: 'success' })
  } catch (e) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  }
}

function openPasswordLink(u: AdminUser): void {
  passwordLinkUser.value = { id: u.id, email: u.email }
  passwordLinkOpen.value = true
}

function getRowItems(row: Row<AdminUser>): AdminUserRowMenuItem[] {
  const u = row.original
  const items: AdminUserRowMenuItem[] = [{ type: 'label', label: 'Actions' }]
  if (u.status !== 'approved') {
    items.push({
      label: 'Approuver',
      icon: 'i-lucide-check-circle-2',
      onSelect: () => onApprove(u),
    })
  }
  if (u.status !== 'rejected' && !u.is_admin) {
    items.push({
      label: 'Refuser',
      icon: 'i-lucide-x-circle',
      onSelect: () => onReject(u),
    })
  }
  if (u.status === 'approved' && !u.is_admin) {
    items.push({
      label: "Bannir l'accès",
      icon: 'i-lucide-shield-off',
      onSelect: () => onBan(u),
    })
  }
  if (!u.is_admin) {
    items.push({ type: 'separator' })
    items.push({
      label: 'Générer un lien mot de passe',
      icon: 'i-lucide-link',
      onSelect: () => openPasswordLink(u),
    })
    items.push({ type: 'separator' })
    items.push({
      label: "Supprimer l'utilisateur",
      icon: 'i-lucide-trash-2',
      color: 'error',
      onSelect: () => onDelete(u),
    })
  }
  return items
}

const columns: TableColumn<AdminUser>[] = [
  {
    accessorKey: 'id',
    header: 'ID',
    cell: ({ row }) =>
      h('div', { class: 'flex items-center gap-3' }, [
        h(UserAvatar, { userId: row.original.id, size: 'md' }),
        h('span', { class: 'text-muted tabular-nums' }, `#${row.original.id}`),
      ]),
  },
  {
    accessorKey: 'email',
    header: 'E-mail',
    cell: ({ row }) =>
      h('div', { class: 'min-w-0' }, [
        h('p', { class: 'font-medium text-highlighted truncate' }, row.original.email),
        row.original.is_admin
          ? h(
              UBadge,
              {
                size: 'sm',
                color: 'primary',
                variant: 'subtle',
                class: 'mt-1',
              },
              () => 'Admin',
            )
          : null,
      ]),
  },
  {
    accessorKey: 'vinted_email',
    header: 'Vinted',
    cell: ({ row }) => {
      const u = row.original
      return h('div', { class: 'flex flex-col text-sm min-w-0' }, [
        h('span', { class: 'truncate text-muted' }, u.vinted_email || '—'),
        h(
          'span',
          { class: u.vinted_linked ? 'text-success text-xs' : 'text-muted text-xs' },
          u.vinted_linked ? 'Compte lié' : 'Non lié',
        ),
      ])
    },
  },
  {
    accessorKey: 'vinted_enabled',
    header: 'Vinted activé',
    cell: ({ row }) =>
      h(
        UBadge,
        {
          color: row.original.vinted_enabled ? 'success' : 'neutral',
          variant: 'subtle',
        },
        () => (row.original.vinted_enabled ? 'Oui' : 'Non'),
      ),
  },
  {
    accessorKey: 'ebay_enabled',
    header: 'eBay activé',
    cell: ({ row }) =>
      h(
        UBadge,
        {
          color: row.original.ebay_enabled ? 'success' : 'neutral',
          variant: 'subtle',
        },
        () => (row.original.ebay_enabled ? 'Oui' : 'Non'),
      ),
  },
  {
    accessorKey: 'margin_percent',
    header: 'Marge',
    cell: ({ row }) => h('span', { class: 'tabular-nums' }, eur.format((row.original.margin_percent ?? 0) / 100)),
  },
  {
    accessorKey: 'status',
    header: 'Statut',
    filterFn: 'equals',
    cell: ({ row }) => h(UserStatusBadge, { status: row.original.status }),
  },
  {
    accessorKey: 'request_message',
    header: 'Message de demande',
    cell: ({ row }) => {
      const msg = row.original.request_message
      if (!msg) {
        return h('span', { class: 'text-muted text-xs' }, '—')
      }
      return h(
        'p',
        {
          class: 'text-sm text-muted line-clamp-2 max-w-[280px]',
          title: msg,
        },
        msg,
      )
    },
  },
  {
    id: 'actions',
    cell: ({ row }) =>
      h(
        'div',
        { class: 'text-right' },
        h(
          UDropdownMenu,
          {
            content: { align: 'end' },
            items: getRowItems(row),
          },
          () =>
            h(UButton, {
              icon: 'i-lucide-ellipsis-vertical',
              color: 'neutral',
              variant: 'ghost',
              class: 'ml-auto',
            }),
        ),
      ),
  },
]

const filteredUsers: ComputedRef<AdminUser[]> = computed(() => {
  const q = search.value.trim().toLowerCase()
  return users.value.filter((u) => {
    if (statusFilter.value !== 'all' && u.status !== statusFilter.value) {
      return false
    }
    if (!q) {
      return true
    }
    return (
      u.email.toLowerCase().includes(q) ||
      (u.vinted_email ?? '').toLowerCase().includes(q) ||
      (u.request_message ?? '').toLowerCase().includes(q)
    )
  })
})

const statusItems = [
  { label: 'Tous les statuts', value: 'all' },
  { label: 'En attente', value: 'pending' },
  { label: 'Approuvé', value: 'approved' },
  { label: 'Refusé', value: 'rejected' },
  { label: 'Banni', value: 'banned' },
]

const counts: ComputedRef<{ pending: number; approved: number; banned: number }> = computed(() => ({
  pending: users.value.filter((u) => u.status === 'pending').length,
  approved: users.value.filter((u) => u.status === 'approved').length,
  banned: users.value.filter((u) => u.status === 'banned').length,
}))

onMounted((): void => {
  void load()
})
</script>
