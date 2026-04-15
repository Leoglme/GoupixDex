<script setup lang="ts">
definePageMeta({ middleware: 'auth' })

useGoupixPageSeo(
  'Création groupée d’articles',
  'Ajoutez plusieurs cartes Pokémon TCG en une session GoupixDex et lancez éventuellement une publication Vinted groupée depuis l’app desktop.'
)

type ArticleFormExpose = {
  buildCreateFormData: () => FormData
}

const { createArticle, startVintedBatch } = useArticles()
const toast = useToast()
const { isDesktopApp } = useDesktopRuntime()

let nextSlotId = 1
const formSlots = ref([{ id: 0 }])
const formRefs = ref<(ArticleFormExpose | null)[]>([])

function bindFormRef(idx: number, el: unknown) {
  while (formRefs.value.length <= idx) {
    formRefs.value.push(null)
  }
  formRefs.value[idx] = (el as ArticleFormExpose | null) ?? null
}

function addForm() {
  formSlots.value.push({ id: nextSlotId++ })
}

function removeForm(idx: number) {
  if (formSlots.value.length <= 1) {
    return
  }
  formSlots.value.splice(idx, 1)
  formRefs.value.splice(idx, 1)
}

const batchVinted = ref(true)
const submitting = ref(false)

async function submitAll() {
  const createdIds: number[] = []
  submitting.value = true
  try {
    for (let i = 0; i < formSlots.value.length; i++) {
      const comp = formRefs.value[i]
      if (!comp?.buildCreateFormData) {
        toast.add({
          title: `Formulaire ${i + 1}`,
          description: 'Chargement incomplet — réessayez.',
          color: 'error'
        })
        return
      }
      const fd = comp.buildCreateFormData()
      const title = fd.get('title')?.toString()?.trim()
      const purchase = fd.get('purchase_price')?.toString()?.trim()
      const images = fd.getAll('images') as File[]
      if (!title || !purchase || !images.length) {
        toast.add({
          title: `Article ${i + 1} incomplet`,
          description: 'Titre, prix d\'achat et au moins une image sont requis.',
          color: 'error'
        })
        return
      }
      const { article } = await createArticle(fd)
      createdIds.push(article.id)
    }

    toast.add({
      title: `${createdIds.length} article(s) créé(s)`,
      color: 'success'
    })

    if (isDesktopApp.value && batchVinted.value && createdIds.length) {
      try {
        const { job_id, stream_path } = await startVintedBatch(createdIds)
        await navigateTo({
          path: '/articles/vinted-logs',
          query: { job: job_id }
        })
      } catch (e) {
        toast.add({
          title: 'Création OK — lot Vinted non lancé',
          description: apiErrorMessage(e),
          color: 'warning'
        })
        await navigateTo('/articles')
      }
    } else {
      await navigateTo('/articles')
    }
  } catch (e) {
    toast.add({
      title: 'Erreur lors de la création',
      description: apiErrorMessage(e),
      color: 'error'
    })
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <UDashboardPanel id="articles-batch-create">
    <template #header>
      <UDashboardNavbar title="Création groupée">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <div class="flex flex-wrap items-center gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              icon="i-lucide-list"
              to="/articles"
            >
              Liste
            </UButton>
            <UButton
              color="neutral"
              variant="subtle"
              icon="i-lucide-plus"
              @click="addForm"
            >
              Ajouter un formulaire
            </UButton>
          </div>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="p-4 sm:p-6 max-w-4xl space-y-6">
        <UCard>
          <p class="text-sm text-muted">
            Remplissez plusieurs fiches puis validez une seule fois. Les articles sont créés à la suite ;
            si vous cochez l’option ci-dessous, une <strong>seule session</strong> Chrome enchaîne les publications Vinted.
          </p>
          <div class="mt-4 rounded-lg border border-default p-4">
            <UCheckbox
              v-model="batchVinted"
              :disabled="!isDesktopApp"
              label="Lancer la publication Vinted groupée après création (une connexion)"
            />
            <p v-if="!isDesktopApp" class="mt-2 text-sm text-muted">
              Disponible uniquement dans l’app desktop.
              <NuxtLink to="/downloads" class="underline underline-offset-2">
                Télécharger l’app
              </NuxtLink>
            </p>
          </div>
        </UCard>

        <div
          v-for="(slot, idx) in formSlots"
          :key="slot.id"
          class="space-y-2"
        >
          <UCard>
            <template #header>
              <div class="flex flex-wrap items-center justify-between gap-2">
                <p class="font-medium text-highlighted">
                  Article {{ idx + 1 }}
                </p>
                <UButton
                  v-if="formSlots.length > 1"
                  color="error"
                  variant="ghost"
                  size="xs"
                  icon="i-lucide-trash-2"
                  @click="removeForm(idx)"
                >
                  Retirer ce bloc
                </UButton>
              </div>
            </template>
            <ArticleForm
              :ref="(el) => bindFormRef(idx, el)"
              mode="create"
              :loading="submitting"
              :hide-vinted-option="true"
              :show-submit-button="false"
            />
          </UCard>
        </div>

        <div class="flex flex-wrap items-center gap-3">
          <UButton
            color="primary"
            size="lg"
            icon="i-lucide-upload-cloud"
            :loading="submitting"
            @click="submitAll"
          >
            Créer {{ formSlots.length }} article(s)
            <span v-if="batchVinted && isDesktopApp"> et lancer Vinted</span>
          </UButton>
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>
