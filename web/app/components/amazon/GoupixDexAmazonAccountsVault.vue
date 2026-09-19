<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <p class="text-muted text-sm">
        Email et mot de passe chiffrés sur le serveur. Un profil Chrome local par compte.
      </p>
      <UButton color="primary" icon="i-lucide-plus" size="sm" @click="openCreate"> Ajouter </UButton>
    </div>

    <UAlert
      v-if="!isDesktopApp"
      color="info"
      variant="subtle"
      icon="i-lucide-monitor-smartphone"
      title="Application bureau"
      description="Connexion Chrome et invitations : worker local (app desktop uniquement)."
    />

    <UAlert v-else-if="loadError" color="warning" variant="subtle" icon="i-lucide-unplug" :title="loadError" />

    <section v-if="formOpen" class="border-default bg-elevated/30 space-y-4 rounded-lg border p-4">
      <div class="flex items-start justify-between gap-2">
        <p class="text-highlighted text-sm font-medium">
          {{ formMode === 'create' ? 'Ajouter un compte Amazon' : 'Modifier le compte' }}
        </p>
        <UButton color="neutral" variant="ghost" icon="i-lucide-x" size="xs" aria-label="Fermer" @click="closeForm" />
      </div>
      <template v-if="formMode === 'edit'">
        <form class="space-y-3" @submit.prevent="submitForm">
          <UFormField label="Email Amazon.fr" required>
            <UInput v-model="form.amazon_email" type="email" required class="w-full" />
          </UFormField>
          <UFormField label="Mot de passe" description="Laisser vide pour ne pas changer.">
            <UInput v-model="form.password" type="password" class="w-full" autocomplete="off" />
          </UFormField>
          <div class="flex justify-end gap-2 pt-1">
            <UButton type="button" color="neutral" variant="outline" @click="closeForm"> Annuler </UButton>
            <UButton type="submit" color="primary" :loading="formSaving"> Enregistrer </UButton>
          </div>
        </form>
      </template>

      <template v-else>
        <UTabs v-model="createTab" :items="createTabItems" class="w-full" />
        <form v-if="createTab === 'existing'" class="mt-3 space-y-3" @submit.prevent="submitForm">
          <UFormField label="Email Amazon.fr" required>
            <UInput v-model="form.amazon_email" type="email" required class="w-full" />
          </UFormField>
          <UFormField label="Mot de passe" description="Stocké chiffré sur le serveur.">
            <UInput v-model="form.password" type="password" class="w-full" autocomplete="off" />
          </UFormField>
          <div class="flex justify-end gap-2 pt-1">
            <UButton type="button" color="neutral" variant="outline" @click="closeForm"> Annuler </UButton>
            <UButton type="submit" color="primary" :loading="formSaving"> Enregistrer </UButton>
          </div>
        </form>
        <div v-else class="mt-3 space-y-3">
          <UFormField label="Nombre de comptes">
            <UInput v-model.number="provisionCount" type="number" min="1" max="10" class="w-full max-w-[8rem]" />
          </UFormField>
          <div class="flex justify-end gap-2 pt-1">
            <UButton type="button" color="neutral" variant="outline" @click="closeForm"> Annuler </UButton>
            <UButton
              type="button"
              color="primary"
              icon="i-lucide-sparkles"
              :loading="provisionRunning"
              :disabled="!isDesktopApp"
              @click="runProvision"
            >
              Générer et ouvrir Chrome
            </UButton>
          </div>
        </div>
      </template>
    </section>

    <div v-if="loading" class="text-muted text-sm">Chargement des comptes…</div>

    <ul v-else-if="accounts.length" class="space-y-2">
      <li v-for="acc in accounts" :key="acc.id" class="border-default/60 flex gap-3 rounded-lg border px-3 py-2.5">
        <div class="min-w-0 flex-1 space-y-1">
          <span class="text-highlighted block truncate text-sm font-medium">
            {{ acc.amazon_email }}
          </span>
          <div class="flex min-w-0 items-center gap-1">
            <span
              class="text-muted min-w-0 truncate font-mono text-sm tracking-wider"
              :title="isPasswordVisible(acc.id) ? passwordByAccountId[acc.id] : undefined"
            >
              {{ passwordDisplay(acc.id) }}
            </span>
            <UButton
              size="xs"
              color="neutral"
              variant="ghost"
              class="shrink-0"
              :icon="isPasswordVisible(acc.id) ? 'i-lucide-eye-off' : 'i-lucide-eye'"
              :loading="passwordLoadingId === acc.id"
              :aria-label="isPasswordVisible(acc.id) ? 'Masquer le mot de passe' : 'Afficher le mot de passe'"
              @click="togglePasswordVisibility(acc.id)"
            />
          </div>
        </div>

        <div class="flex shrink-0 flex-wrap items-start justify-end gap-1.5">
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-pencil"
            aria-label="Modifier"
            @click="openEdit(acc)"
          />
          <UButton
            size="xs"
            color="error"
            variant="ghost"
            icon="i-lucide-trash-2"
            aria-label="Supprimer"
            @click="confirmDelete(acc)"
          />
        </div>
      </li>
    </ul>

    <GoupixDexConfirmModal
      v-model:open="deleteModalOpen"
      title="Supprimer ce compte Amazon ?"
      :description="deleteModalDescription"
      confirm-label="Supprimer"
      confirm-color="error"
      :loading="deleteSubmitting"
      @confirm="submitDelete"
      @cancel="clearDeleteTarget"
    />

    <GoupixDexConfirmModal
      v-model:open="provisionContinueOpen"
      title="Compte Amazon suivant"
      :description="provisionContinueDescription"
      confirm-label="Compte suivant"
      cancel-label="Arrêter ici"
      confirm-color="primary"
      @confirm="resolveProvisionContinue(true)"
      @cancel="resolveProvisionContinue(false)"
    />

    <GoupixDexConfirmModal
      v-model:open="provisionSaveOpen"
      title="Enregistrer dans le coffre ?"
      :description="provisionSaveDescription"
      confirm-label="Compte créé sur Amazon — Enregistrer"
      cancel-label="Annuler (ne pas enregistrer)"
      confirm-color="primary"
      :loading="provisionSaveLoading"
      @confirm="resolveProvisionSave(true)"
      @cancel="resolveProvisionSave(false)"
    />
  </div>
</template>

<script setup lang="ts">
import type { Ref } from 'vue'
import type { AmazonVaultAccount } from '~/types/amazonAccounts'
import { generateAmazonProvisionEmail, generateAmazonProvisionPassword } from '~/utils/amazonAccountProvision'

const MASKED_PASSWORD = '••••••••••••'

const emit = defineEmits<{
  changed: []
}>()

const { isDesktopApp } = useDesktopRuntime()
const { fetchOverview, createAccount, updateAccount, deleteAccount, revealCredentials, setActiveAccount } =
  useAmazonAccounts()
const { openProvisionRegister, discardProvisionStaging, claimStagingProfile, closeLoginBrowser, fetchWorkerMeta } =
  useAmazonWorker()
const toast = useToast()

const loading: Ref<boolean> = ref(false)
const loadError: Ref<string | null> = ref(null)
const accounts: Ref<AmazonVaultAccount[]> = ref([])

const formOpen = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const editingId = ref<number | null>(null)
const formSaving = ref(false)
const form = ref({ amazon_email: '', password: '' })
const createTab = ref<'existing' | 'provision'>('existing')
const createTabItems = [
  { label: 'Compte existant', value: 'existing' },
  { label: 'Créer sur Amazon', value: 'provision' },
]
const provisionCount = ref(1)
const provisionRunning = ref(false)
const provisionContinueOpen = ref(false)
const provisionContinueDescription = ref('')
let provisionContinueResolver: ((cont: boolean) => void) | null = null

const provisionSaveOpen = ref(false)
const provisionSaveDescription = ref('')
const provisionSaveLoading = ref(false)
let provisionSaveResolver: ((save: boolean) => void) | null = null
const deleteModalOpen = ref(false)
const deleteTarget: Ref<AmazonVaultAccount | null> = ref(null)
const deleteSubmitting = ref(false)

const deleteModalDescription = computed(() => {
  const email = deleteTarget.value?.amazon_email
  if (!email) {
    return 'Cette action est irréversible.'
  }
  return `Le compte ${email} sera retiré du coffre GoupixDex (profil Chrome local conservé sur ce poste).`
})

const passwordByAccountId: Ref<Record<number, string>> = ref({})
const passwordVisibleByAccountId: Ref<Record<number, boolean>> = ref({})
const passwordLoadingId: Ref<number | null> = ref(null)

function notifyChanged(): void {
  emit('changed')
}

function clearPasswordRevealState(accountId?: number): void {
  if (accountId != null) {
    const { [accountId]: _p, ...restPw } = passwordByAccountId.value
    const { [accountId]: _v, ...restVis } = passwordVisibleByAccountId.value
    passwordByAccountId.value = restPw
    passwordVisibleByAccountId.value = restVis
    return
  }
  passwordByAccountId.value = {}
  passwordVisibleByAccountId.value = {}
}

function isPasswordVisible(accountId: number): boolean {
  return Boolean(passwordVisibleByAccountId.value[accountId])
}

function passwordDisplay(accountId: number): string {
  if (isPasswordVisible(accountId) && passwordByAccountId.value[accountId]) {
    return passwordByAccountId.value[accountId]
  }
  return MASKED_PASSWORD
}

async function togglePasswordVisibility(accountId: number): Promise<void> {
  if (isPasswordVisible(accountId)) {
    passwordVisibleByAccountId.value = { ...passwordVisibleByAccountId.value, [accountId]: false }
    return
  }

  if (!passwordByAccountId.value[accountId]) {
    passwordLoadingId.value = accountId
    try {
      const cred = await revealCredentials(accountId)
      passwordByAccountId.value = { ...passwordByAccountId.value, [accountId]: cred.password }
    } catch (e: unknown) {
      toast.add({ title: 'Impossible d’afficher le mot de passe', description: apiErrorMessage(e), color: 'error' })
      return
    } finally {
      passwordLoadingId.value = null
    }
  }

  passwordVisibleByAccountId.value = { ...passwordVisibleByAccountId.value, [accountId]: true }
}

async function loadVault(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    const overview = await fetchOverview()
    accounts.value = overview.accounts
  } catch (e: unknown) {
    loadError.value = apiErrorMessage(e)
  } finally {
    loading.value = false
  }
}

function closeForm(): void {
  formOpen.value = false
}

function openCreate(): void {
  formMode.value = 'create'
  editingId.value = null
  createTab.value = 'existing'
  form.value = { amazon_email: '', password: '' }
  provisionCount.value = 1
  formOpen.value = true
}

function workerStaleMessage(): string {
  return 'Worker Amazon obsolète : quitte GoupixDex desktop complètement puis rouvre l’app. En dev, lance `python desktop_amazon_server.py` dans le dossier api (ou rebuild le sidecar).'
}

function provisionErrorMessage(e: unknown): string {
  const err = e as { message?: string; code?: string; response?: unknown }
  if (
    !err.response &&
    (err.code === 'ERR_NETWORK' ||
      err.code === 'ECONNREFUSED' ||
      err.message === 'Network Error' ||
      err.message?.includes('Network Error'))
  ) {
    return (
      'Worker Amazon injoignable (127.0.0.1:18768). ' +
      'Relance l’app desktop (Tauri) pour relancer le worker, ou « Redémarrer les workers » si disponible.'
    )
  }
  const base = apiErrorMessage(e)
  if (base === 'Not Found' || base.toLowerCase().includes('not found')) {
    return workerStaleMessage()
  }
  return base
}

function withWorkerTimeout<T>(promise: Promise<T>, ms: number, label: string): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`${label} (délai dépassé).`)), ms)
    promise.then(
      (v) => {
        clearTimeout(timer)
        resolve(v)
      },
      (e: unknown) => {
        clearTimeout(timer)
        reject(e)
      },
    )
  })
}

async function runProvision(): Promise<void> {
  if (!isDesktopApp.value) {
    toast.add({ title: 'Réservé à l’app desktop', color: 'warning' })
    return
  }
  const meta = await fetchWorkerMeta()
  if (!meta?.features?.includes('provision-open-register')) {
    toast.add({ title: 'Worker à redémarrer', description: workerStaleMessage(), color: 'warning' })
    return
  }
  const count = Math.min(10, Math.max(1, Math.round(provisionCount.value) || 1))
  provisionRunning.value = true
  try {
    for (let i = 0; i < count; i++) {
      const email = generateAmazonProvisionEmail()
      const password = generateAmazonProvisionPassword()

      const res = await withWorkerTimeout(
        openProvisionRegister({ email, password }),
        130_000,
        'Ouverture Chrome Amazon',
      )
      if (!res.success || !res.email_prefilled) {
        try {
          await discardProvisionStaging()
        } catch {
          /* ignore */
        }
        try {
          await closeLoginBrowser()
        } catch {
          /* ignore */
        }
        throw new Error(res.message || 'Préremplissage Amazon impossible.')
      }

      const save = await askProvisionSaveToVault(email)
      if (!save) {
        try {
          await discardProvisionStaging()
        } catch {
          /* ignore */
        }
        try {
          await closeLoginBrowser()
        } catch {
          /* ignore */
        }
        break
      }

      provisionSaveLoading.value = true
      try {
        const created = await createAccount({ amazon_email: email, password })
        await claimStagingProfile(created.id)
        await setActiveAccount(created.id)
        passwordByAccountId.value = { ...passwordByAccountId.value, [created.id]: password }
        passwordVisibleByAccountId.value = { ...passwordVisibleByAccountId.value, [created.id]: true }
        toast.add({
          title: `Compte ${i + 1}/${count} enregistré`,
          description: email,
          color: 'success',
        })
      } finally {
        provisionSaveLoading.value = false
      }

      if (i < count - 1) {
        const cont = await askProvisionContinue(email, i + 2, count)
        if (!cont) {
          break
        }
      }
    }
    formOpen.value = false
    await loadVault()
    notifyChanged()
  } catch (e: unknown) {
    try {
      await closeLoginBrowser()
    } catch {
      /* ignore */
    }
    toast.add({ title: 'Création impossible', description: provisionErrorMessage(e), color: 'error' })
  } finally {
    provisionRunning.value = false
  }
}

function openEdit(acc: AmazonVaultAccount): void {
  formMode.value = 'edit'
  editingId.value = acc.id
  form.value = { amazon_email: acc.amazon_email, password: '' }
  formOpen.value = true
}

async function submitForm(): Promise<void> {
  formSaving.value = true
  try {
    if (formMode.value === 'create') {
      if (!form.value.password.trim()) {
        toast.add({ title: 'Mot de passe requis', color: 'warning' })
        return
      }
      await createAccount({
        amazon_email: form.value.amazon_email.trim(),
        password: form.value.password,
      })
      toast.add({ title: 'Compte ajouté', color: 'success' })
    } else if (editingId.value != null) {
      await updateAccount(editingId.value, {
        amazon_email: form.value.amazon_email.trim(),
        ...(form.value.password.trim() ? { password: form.value.password } : {}),
      })
      clearPasswordRevealState(editingId.value)
      toast.add({ title: 'Compte mis à jour', color: 'success' })
    }
    formOpen.value = false
    await loadVault()
    notifyChanged()
  } catch (e: unknown) {
    toast.add({ title: 'Erreur', description: apiErrorMessage(e), color: 'error' })
  } finally {
    formSaving.value = false
  }
}

function askProvisionContinue(email: string, nextIndex: number, total: number): Promise<boolean> {
  provisionContinueDescription.value = `Terminez l’inscription Amazon pour ${email}, puis ouvrez le compte ${nextIndex}/${total}.`
  provisionContinueOpen.value = true
  return new Promise((resolve) => {
    provisionContinueResolver = resolve
  })
}

function resolveProvisionContinue(cont: boolean): void {
  provisionContinueOpen.value = false
  provisionContinueResolver?.(cont)
  provisionContinueResolver = null
}

function askProvisionSaveToVault(email: string): Promise<boolean> {
  provisionSaveDescription.value =
    `Terminez l’inscription sur Amazon (SMS / CAPTCHA) pour ${email}. ` +
    'Enregistrez dans le coffre uniquement lorsque le compte Amazon fonctionne.'
  provisionSaveOpen.value = true
  return new Promise((resolve) => {
    provisionSaveResolver = resolve
  })
}

function resolveProvisionSave(save: boolean): void {
  provisionSaveOpen.value = false
  provisionSaveResolver?.(save)
  provisionSaveResolver = null
}

function confirmDelete(acc: AmazonVaultAccount): void {
  deleteTarget.value = acc
  deleteModalOpen.value = true
}

function clearDeleteTarget(): void {
  if (!deleteSubmitting.value) {
    deleteTarget.value = null
  }
}

async function submitDelete(): Promise<void> {
  const acc = deleteTarget.value
  if (!acc) {
    return
  }
  deleteSubmitting.value = true
  try {
    await deleteAccount(acc.id)
    clearPasswordRevealState(acc.id)
    toast.add({ title: 'Compte supprimé', color: 'success' })
    deleteModalOpen.value = false
    deleteTarget.value = null
    await loadVault()
    notifyChanged()
  } catch (e: unknown) {
    toast.add({ title: 'Suppression impossible', description: apiErrorMessage(e), color: 'error' })
  } finally {
    deleteSubmitting.value = false
  }
}

async function reload(): Promise<void> {
  clearPasswordRevealState()
  await loadVault()
}

defineExpose({ reload, openCreate })
</script>
