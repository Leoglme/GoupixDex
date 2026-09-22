<template>
  <div>
    <input ref="fileInputEl" type="file" accept="image/*,.heic,.heif" class="hidden" @change="onFileInput" />

    <div class="mb-5 flex flex-wrap items-center justify-between gap-3">
      <div class="flex min-w-0 items-center gap-3">
        <NuxtLink
          :to="backHref"
          aria-label="Retour au classeur"
          title="Retour au classeur"
          class="text-muted flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-(--app-line) transition hover:border-(--app-ink-soft) hover:text-(--app-ink)"
        >
          <UIcon name="i-lucide-chevron-left" class="size-4" aria-hidden />
        </NuxtLink>
        <div class="min-w-0">
          <h1 class="font-display truncate text-2xl font-bold tracking-tight">Personnaliser « {{ name }} »</h1>
          <p class="text-muted text-xs">L'aperçu suit tes choix ; rien n'est enregistré avant « Enregistrer ».</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <NuxtLink :to="backHref" class="dialog-btn-secondary">Annuler</NuxtLink>
        <button type="button" class="dialog-btn-primary" :disabled="saving || busy" @click="save">
          <UIcon v-if="saving" name="i-lucide-loader-2" class="size-4 animate-spin" />
          {{ saving ? 'Enregistrement…' : 'Enregistrer' }}
        </button>
      </div>
    </div>

    <div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_min(100%,28rem)]">
      <div class="lg:sticky lg:top-6 lg:self-start">
        <GoupixDexCollectionViewTabs v-model="preview" :items="previewTabItems" class="mb-3" />

        <p class="mb-3 text-xs text-(--app-faint)">
          {{ preview === 'ferme' ? 'Tu personnalises la couverture.' : 'Tu personnalises les pages et les anneaux.' }}
        </p>

        <div
          class="binder-stage app-card flex justify-center p-6"
          :class="preview === 'ferme' ? 'items-start' : 'items-center'"
        >
          <template v-if="preview === 'ferme'">
            <div class="relative w-full max-w-sm">
              <GoupixDexBinderCover
                :cover-style="style"
                :covers="previewCovers"
                :name="name"
                :color-hex="colorHex"
                :texture="design.coverTexture"
                :layout="coverRender"
              />
              <div
                v-if="isCustom"
                class="absolute inset-0 grid grid-cols-3 grid-rows-3 gap-[2%] p-[5%]"
                role="group"
                aria-label="Zones de la couverture"
              >
                <button
                  v-for="z in ZONES"
                  :key="z"
                  type="button"
                  :title="ZONE_LABELS[z]"
                  :aria-pressed="z === zone"
                  class="rounded-md border transition"
                  :class="
                    z === zone
                      ? 'border-(--app-accent) bg-(--app-accent-soft) ring-2 ring-(--app-accent-soft)'
                      : layout.zones[z]
                        ? 'border-white/25 hover:border-white/60'
                        : 'border-dashed border-white/20 hover:border-white/60 hover:bg-white/5'
                  "
                  @click="zone = z"
                />
              </div>
            </div>
          </template>
          <template v-else>
            <div class="mx-auto w-full max-w-4xl">
              <div class="flex items-stretch justify-center">
                <div class="relative min-w-0 flex-1 rounded-l-lg border shadow-(--app-shadow-soft)" :class="sheet.page">
                  <span
                    v-for="(t, ri) in ringPos"
                    :key="`l-${ri}`"
                    aria-hidden
                    class="absolute right-1.5 h-2 w-2 -translate-y-1/2 rounded-full"
                    :class="sheet.holes"
                    :style="{ top: `${t * 100}%` }"
                  />
                  <div
                    class="grid gap-1.5"
                    :style="{
                      gridTemplateColumns: `repeat(${gridDef.cols}, minmax(0, 1fr))`,
                      padding: '8px 8px 14px 16px',
                    }"
                  >
                    <div
                      v-for="k in pocketsPerPage(gridDef)"
                      :key="`l-${k}`"
                      class="relative aspect-[63/88] rounded shadow-[inset_0_2px_6px_rgba(0,0,0,.4)] ring-1"
                      :class="[sheet.pocketBg, sheet.pocketRing]"
                    >
                      <div v-if="sampleCards[k - 1]" class="absolute inset-[3%]">
                        <div class="card-tile h-full w-full">
                          <GoupixDexBinderCardImage
                            :src="sampleCards[k - 1]!.image_url"
                            :alt="sampleCards[k - 1]!.name"
                          />
                        </div>
                      </div>
                      <span
                        v-if="sheen"
                        aria-hidden
                        class="pointer-events-none absolute inset-0 rounded bg-gradient-to-br"
                        :class="sheen"
                      />
                    </div>
                  </div>
                  <span
                    v-if="design.pageNumbers"
                    class="num absolute right-2.5 bottom-1 text-[9px]"
                    :class="sheet.number"
                  >
                    1
                  </span>
                </div>

                <div class="relative z-10 -mx-px w-5 shrink-0 self-stretch">
                  <div
                    class="absolute inset-x-0 -inset-y-1 overflow-hidden rounded bg-(--app-surface-2)"
                    :style="colorHex ? { backgroundColor: colorHex } : undefined"
                  >
                    <div class="absolute inset-0 bg-gradient-to-r from-black/40 via-white/10 to-black/45" />
                    <span v-if="textureClass" aria-hidden class="absolute inset-0" :class="textureClass" />
                  </div>
                  <span
                    v-for="(t, ri) in ringPos"
                    :key="`s-${ri}`"
                    aria-hidden
                    class="absolute left-1/2 h-2.5 w-9 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 shadow-[0_1px_2px_rgba(0,0,0,.6)]"
                    :style="{ top: `${t * 100}%`, borderColor: ringColor }"
                  />
                </div>

                <div class="relative min-w-0 flex-1 rounded-r-lg border shadow-(--app-shadow-soft)" :class="sheet.page">
                  <span
                    v-for="(t, ri) in ringPos"
                    :key="`r-${ri}`"
                    aria-hidden
                    class="absolute left-1.5 h-2 w-2 -translate-y-1/2 rounded-full"
                    :class="sheet.holes"
                    :style="{ top: `${t * 100}%` }"
                  />
                  <div
                    class="grid gap-1.5"
                    :style="{
                      gridTemplateColumns: `repeat(${gridDef.cols}, minmax(0, 1fr))`,
                      padding: '8px 16px 14px 8px',
                    }"
                  >
                    <div
                      v-for="k in pocketsPerPage(gridDef)"
                      :key="`r-${k}`"
                      class="relative aspect-[63/88] rounded shadow-[inset_0_2px_6px_rgba(0,0,0,.4)] ring-1"
                      :class="[sheet.pocketBg, sheet.pocketRing]"
                    >
                      <span
                        v-if="sheen"
                        aria-hidden
                        class="pointer-events-none absolute inset-0 rounded bg-gradient-to-br"
                        :class="sheen"
                      />
                    </div>
                  </div>
                  <span
                    v-if="design.pageNumbers"
                    class="num absolute bottom-1 left-2.5 text-[9px]"
                    :class="sheet.number"
                  >
                    2
                  </span>
                </div>
              </div>
              <p class="mt-3 text-center text-xs text-(--app-faint)">
                Aperçu d'une double page · {{ gridDef.cols }}×{{ gridDef.rows }}
              </p>
            </div>
          </template>
        </div>
      </div>

      <div class="flex flex-col gap-5">
        <template v-if="preview === 'ferme'">
          <section class="app-card space-y-5 p-5">
            <p class="app-label">Style de couverture</p>
            <GoupixDexBinderEditorField label="Type de couverture">
              <GoupixDexBinderOptionChips
                label="Style de couverture"
                :options="styleLabels"
                :model-value="style"
                @update:model-value="onStylePick"
              />
            </GoupixDexBinderEditorField>
            <GoupixDexBinderEditorField label="Couleur de tranche">
              <GoupixDexBinderColorPicker
                label="Couleur de tranche"
                :colors="binderColorSwatches"
                :model-value="colorHex"
                with-neutral
                @update:model-value="onSpineColorPick"
              />
            </GoupixDexBinderEditorField>
            <GoupixDexBinderEditorField label="Matière">
              <GoupixDexBinderOptionChips
                spread
                label="Matière"
                :options="COVER_TEXTURES"
                :model-value="design.coverTexture"
                @update:model-value="setD({ coverTexture: $event as typeof design.coverTexture })"
              />
            </GoupixDexBinderEditorField>
          </section>

          <template v-if="isCustom">
            <section class="app-card space-y-5 p-5">
              <p class="app-label">Fond de la couverture</p>
              <GoupixDexBinderEditorField label="Type de fond">
                <GoupixDexBinderOptionChips
                  spread
                  label="Type de fond"
                  :options="bgKinds"
                  :model-value="layout.bg.kind"
                  @update:model-value="onBgKindPick"
                />
              </GoupixDexBinderEditorField>
              <div class="flex flex-col gap-5">
                <GoupixDexBinderEditorField label="Couleur de fond" hint="Visible aussi sous une image.">
                  <GoupixDexBinderColorPicker
                    label="Couleur de fond"
                    :colors="bgColorSwatches"
                    :model-value="layout.bg.color"
                    @update:model-value="setBg({ color: $event })"
                  />
                </GoupixDexBinderEditorField>
                <div v-if="layout.bg.kind === 'image'" class="flex flex-wrap items-center gap-3">
                  <div
                    v-if="layout.bg.image && urls[layout.bg.image]"
                    class="h-14 w-14 overflow-hidden rounded-md border border-(--app-line)"
                  >
                    <GoupixDexBinderCardImage :src="urls[layout.bg.image]" alt="" />
                  </div>
                  <button
                    type="button"
                    class="dialog-btn-secondary !px-2.5 text-[13px]"
                    :disabled="busy"
                    @click="pickUpload('bg')"
                  >
                    <UIcon name="i-lucide-image-plus" class="size-3.5" aria-hidden />
                    {{ busy ? 'Envoi…' : "Changer l'image" }}
                  </button>
                  <button
                    type="button"
                    class="dialog-btn-secondary text-muted !px-2.5 text-[13px]"
                    @click="clearBgImage"
                  >
                    <UIcon name="i-lucide-trash-2" class="size-3.5" aria-hidden />
                    Retirer
                  </button>
                </div>
                <GoupixDexBinderEditorCardPicker
                  v-if="layout.bg.kind === 'card'"
                  :cards="cards"
                  :is-selected="(id) => layout.bg.card === id"
                  @pick="(id) => setBg({ card: id })"
                />
                <label v-if="layout.bg.kind !== 'color'" class="text-muted flex items-center gap-3 text-xs">
                  Voile sombre
                  <input
                    type="range"
                    min="0"
                    max="85"
                    :value="layout.bg.dim"
                    class="flex-1 accent-(--app-accent)"
                    @input="setBg({ dim: Number(($event.target as HTMLInputElement).value) })"
                  />
                  <span class="num w-8 text-right">{{ layout.bg.dim }}%</span>
                </label>
              </div>
            </section>

            <section class="app-card p-5">
              <div class="mb-3 flex items-center justify-between gap-3">
                <p class="app-label">Zone · {{ ZONE_LABELS[zone] }}</p>
                <div class="grid grid-cols-3 gap-0.5" role="group" aria-label="Choisir une zone">
                  <button
                    v-for="z in ZONES"
                    :key="z"
                    type="button"
                    :title="ZONE_LABELS[z]"
                    :aria-pressed="z === zone"
                    class="flex h-5 w-5 items-center justify-center rounded-sm border transition"
                    :class="
                      z === zone
                        ? 'border-(--app-accent) bg-(--app-accent-soft)'
                        : 'border-(--app-line) hover:border-(--app-ink-soft)'
                    "
                    @click="zone = z"
                  >
                    <span v-if="layout.zones[z]" class="h-1.5 w-1.5 rounded-full bg-(--app-ink)/70" aria-hidden />
                  </button>
                </div>
              </div>
              <GoupixDexBinderOptionChips
                label="Contenu de la zone"
                :options="elementKinds"
                :model-value="kind"
                @update:model-value="setKind"
              />

              <div v-if="el?.type === 'text'" class="mt-4 flex flex-col gap-3">
                <input
                  v-model="elText"
                  type="text"
                  :maxlength="TEXT_MAX"
                  placeholder="Ton texte…"
                  class="app-input text-[13px]"
                  aria-label="Texte"
                  @input="patchText"
                />
                <div class="flex flex-col gap-4">
                  <GoupixDexBinderEditorField label="Taille">
                    <GoupixDexBinderOptionChips
                      spread
                      label="Taille du texte"
                      :options="TEXT_SIZES"
                      :model-value="el.size"
                      @update:model-value="patchEl({ size: $event as typeof el.size })"
                    />
                  </GoupixDexBinderEditorField>
                  <GoupixDexBinderEditorField label="Police">
                    <GoupixDexBinderOptionChips
                      spread
                      label="Police"
                      :options="FONTS"
                      :model-value="el.font"
                      @update:model-value="patchEl({ font: $event as typeof el.font })"
                    />
                  </GoupixDexBinderEditorField>
                  <GoupixDexBinderEditorField label="Graisse">
                    <GoupixDexBinderOptionChips
                      spread
                      label="Graisse"
                      :options="textWeightOptions"
                      :model-value="el.weight"
                      @update:model-value="patchEl({ weight: $event as 'bold' | 'normal' })"
                    />
                  </GoupixDexBinderEditorField>
                  <GoupixDexBinderEditorField label="Couleur">
                    <GoupixDexBinderColorPicker
                      label="Couleur du texte"
                      :colors="textColorSwatches"
                      :model-value="el.color"
                      @update:model-value="(hex) => hex && patchEl({ color: hex })"
                    />
                  </GoupixDexBinderEditorField>
                </div>
              </div>

              <div v-if="el?.type === 'logo'" class="mt-4 flex flex-col gap-3">
                <div class="relative">
                  <UIcon
                    name="i-lucide-search"
                    class="pointer-events-none absolute top-1/2 left-3 size-3.5 -translate-y-1/2 text-(--app-faint)"
                    aria-hidden
                  />
                  <input
                    v-model="logoQ"
                    type="text"
                    placeholder="Nom de l'extension…"
                    class="app-input !pl-9 text-[13px]"
                    aria-label="Rechercher une extension"
                  />
                </div>
                <div class="grid max-h-56 grid-cols-3 gap-2 overflow-y-auto pr-1">
                  <button
                    v-for="s in logoResults"
                    :key="s.id"
                    type="button"
                    :title="`${s.name} · ${s.serie}`"
                    :aria-pressed="s.id === el.setId"
                    class="flex flex-col items-center gap-1 rounded-lg border p-2 transition"
                    :class="
                      s.id === el.setId
                        ? 'border-(--app-accent)/50 bg-(--app-accent-soft)'
                        : 'border-(--app-line) hover:border-(--app-ink-soft)'
                    "
                    @click="pickLogoSet(s)"
                  >
                    <div class="flex h-10 w-full items-center justify-center">
                      <img
                        v-if="setThumb(s)"
                        :src="setThumb(s)!"
                        alt=""
                        class="max-h-10 max-w-full object-contain"
                        loading="lazy"
                      />
                    </div>
                    <span class="text-muted w-full truncate text-center text-[11px]">{{ s.name }}</span>
                  </button>
                </div>
                <div class="flex flex-col gap-4">
                  <GoupixDexBinderEditorField label="Visuel">
                    <GoupixDexBinderOptionChips
                      spread
                      label="Logo ou symbole"
                      :options="logoVisualOptions"
                      :model-value="logoVisualMode"
                      @update:model-value="onLogoVisualPick"
                    />
                  </GoupixDexBinderEditorField>
                  <GoupixDexBinderEditorField label="Taille">
                    <GoupixDexBinderOptionChips
                      spread
                      label="Taille du logo"
                      :options="ELEMENT_SIZES"
                      :model-value="el.size"
                      @update:model-value="patchEl({ size: $event as typeof el.size })"
                    />
                  </GoupixDexBinderEditorField>
                </div>
              </div>

              <div v-if="el?.type === 'image'" class="mt-4 flex flex-col gap-3">
                <div class="flex flex-wrap items-center gap-3">
                  <div
                    v-if="urls[el.path]"
                    class="h-14 w-14 overflow-hidden border border-(--app-line)"
                    :class="el.shape === 'round' ? 'rounded-full' : 'rounded-md'"
                  >
                    <GoupixDexBinderCardImage :src="urls[el.path]" alt="" />
                  </div>
                  <button
                    type="button"
                    class="dialog-btn-secondary !px-2.5 text-[13px]"
                    :disabled="busy"
                    @click="pickUpload(zone)"
                  >
                    <UIcon name="i-lucide-image-plus" class="size-3.5" aria-hidden />
                    {{ busy ? 'Envoi…' : "Changer l'image" }}
                  </button>
                </div>
                <div class="flex flex-col gap-4">
                  <GoupixDexBinderEditorField label="Taille">
                    <GoupixDexBinderOptionChips
                      spread
                      label="Taille de l'image"
                      :options="ELEMENT_SIZES"
                      :model-value="el.size"
                      @update:model-value="patchEl({ size: $event as typeof el.size })"
                    />
                  </GoupixDexBinderEditorField>
                  <GoupixDexBinderEditorField label="Forme">
                    <GoupixDexBinderOptionChips
                      spread
                      label="Forme"
                      :options="IMAGE_SHAPES"
                      :model-value="el.shape"
                      @update:model-value="patchEl({ shape: $event as typeof el.shape })"
                    />
                  </GoupixDexBinderEditorField>
                </div>
              </div>

              <div v-if="el?.type === 'card'" class="mt-4 flex flex-col gap-3">
                <GoupixDexBinderEditorCardPicker
                  :cards="cards"
                  :is-selected="(id) => el.itemId === id"
                  @pick="(itemId) => patchEl({ itemId })"
                />
                <GoupixDexBinderEditorField label="Taille">
                  <GoupixDexBinderOptionChips
                    spread
                    label="Taille de la carte"
                    :options="ELEMENT_SIZES"
                    :model-value="el.size"
                    @update:model-value="patchEl({ size: $event as typeof el.size })"
                  />
                </GoupixDexBinderEditorField>
              </div>

              <button
                v-if="el"
                type="button"
                class="dialog-btn-secondary text-muted mt-4 !px-2.5 text-[13px]"
                @click="clearZone"
              >
                <UIcon name="i-lucide-trash-2" class="size-3.5" aria-hidden />
                Vider cette zone
              </button>
            </section>
          </template>

          <section v-else-if="maxCovers > 0" class="app-card p-5">
            <div class="mb-2 flex items-baseline justify-between">
              <p class="app-label">Carte{{ maxCovers > 1 ? 's' : '' }} de couverture</p>
              <span class="num text-xs text-(--app-faint)">{{ coverIdsStr.length }}/{{ maxCovers }}</span>
            </div>
            <p class="text-muted mb-3 text-xs">
              {{
                maxCovers > 1
                  ? "L'ordre de sélection définit leur place. Aucune sélection = les premières cartes du classeur."
                  : 'Aucune sélection = la première carte du classeur.'
              }}
            </p>
            <GoupixDexBinderEditorCardPicker
              :cards="cards"
              :is-selected="(id) => coverIdsStr.includes(id)"
              :order="coverOrder"
              @pick="toggleCover"
            />
          </section>
        </template>

        <template v-else>
          <section class="app-card space-y-5 p-5">
            <p class="app-label">Pages</p>
            <GoupixDexBinderEditorField label="Format des feuilles">
              <GoupixDexBinderOptionChips
                spread
                label="Format des feuilles"
                :options="gridOptions"
                :model-value="grid"
                @update:model-value="grid = $event"
              />
            </GoupixDexBinderEditorField>
            <GoupixDexBinderEditorField label="Couleur des feuilles">
              <GoupixDexBinderOptionChips
                spread
                label="Couleur des feuilles"
                :options="pageColorOptions"
                :model-value="design.pageColor"
                @update:model-value="setD({ pageColor: $event as typeof design.pageColor })"
              />
            </GoupixDexBinderEditorField>
            <GoupixDexBinderEditorField label="Finition des pochettes">
              <GoupixDexBinderOptionChips
                spread
                label="Finition des pochettes"
                :options="POCKET_FINISHES"
                :model-value="design.pocketFinish"
                @update:model-value="setD({ pocketFinish: $event as typeof design.pocketFinish })"
              />
            </GoupixDexBinderEditorField>
            <GoupixDexBinderEditorField label="Numéros de page">
              <GoupixDexBinderOptionChips
                spread
                label="Numéros de page"
                :options="numberOptions"
                :model-value="design.pageNumbers ? 'on' : 'off'"
                @update:model-value="setD({ pageNumbers: $event === 'on' })"
              />
            </GoupixDexBinderEditorField>
          </section>

          <section class="app-card space-y-5 p-5">
            <p class="app-label">Anneaux</p>
            <GoupixDexBinderEditorField label="Finition">
              <div class="flex flex-nowrap gap-2" role="group" aria-label="Finition des anneaux">
                <button
                  v-for="r in RING_FINISHES"
                  :key="r.code"
                  type="button"
                  :aria-pressed="design.ringFinish === r.code"
                  class="inline-flex min-w-0 flex-1 items-center justify-center gap-2 rounded-lg border px-2 py-2 text-[13px] font-medium transition focus-visible:ring-2 focus-visible:ring-(--app-accent) focus-visible:outline-none"
                  :class="
                    design.ringFinish === r.code
                      ? 'border-(--app-accent)/50 bg-(--app-accent-soft) text-(--app-accent)'
                      : 'text-muted border-(--app-line) hover:border-(--app-ink-soft) hover:text-(--app-ink)'
                  "
                  @click="setD({ ringFinish: r.code })"
                >
                  <span
                    aria-hidden
                    class="h-4 w-4 shrink-0 rounded-full border-[3px] bg-(--app-surface)"
                    :style="{ borderColor: r.hex }"
                  />
                  {{ r.label }}
                </button>
              </div>
            </GoupixDexBinderEditorField>
            <GoupixDexBinderEditorField label="Nombre d'anneaux">
              <GoupixDexBinderOptionChips
                spread
                label="Nombre d'anneaux"
                :options="ringCountOptions"
                :model-value="String(design.ringCount)"
                @update:model-value="setD({ ringCount: Number($event) as typeof design.ringCount })"
              />
            </GoupixDexBinderEditorField>
          </section>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { EditorCard } from '~/components/binder/GoupixDexBinderEditorCardPicker.vue'
import {
  BG_COLORS,
  ELEMENT_SIZES,
  FONTS,
  IMAGE_SHAPES,
  TEXT_COLORS,
  TEXT_MAX,
  TEXT_SIZES,
  ZONES,
  ZONE_LABELS,
  coverImageResolver,
  coverLayout,
  renderCover,
  type CoverElement,
  type CoverLayout,
  type ZoneKey,
} from '~/utils/binder/binder-cover'
import {
  COVER_TEXTURES,
  PAGE_COLORS,
  POCKET_FINISHES,
  RING_COUNTS,
  RING_FINISHES,
  SHEETS,
  binderDesign,
  coverTextureClass,
  pocketSheen,
  ringHex,
  ringPositions,
  type BinderDesign,
} from '~/utils/binder/binder-design'
import { BINDER_COLORS, binderColorHex } from '~/utils/binder/binder-colors'
import { BINDER_STYLES, binderStyle, binderStyleCovers } from '~/utils/binder/binder-styles'
import { PAGE_GRIDS, pageGrid, pocketsPerPage } from '~/utils/binder/binder-pages'
import { catalogLogoCandidates } from '~/utils/catalogAssets'
import { apiErrorMessage } from '~/composables/useApiError'

export type EditorSet = {
  id: string
  name: string
  serie: string
  logo: string | null
  symbol: string | null
}

const props = defineProps<{
  binderId: number
  name: string
  initialStyle: string | null
  initialColor: string | null
  initialCoverIds: number[]
  initialGrid: string | null
  initialDesign: BinderDesign
  initialLayout: CoverLayout
  initialUrls: Record<string, string>
  cards: EditorCard[]
  sets: EditorSet[]
}>()

const emit = defineEmits<{ saved: [] }>()

const backHref = computed(() => `/classeurs/${props.binderId}`)

const previewTabItems = [
  { label: 'Fermé', value: 'ferme', icon: 'i-lucide-book' },
  { label: 'Ouvert', value: 'ouvert', icon: 'i-lucide-book-open' },
]

const elementKinds = [
  { code: 'none', label: 'Vide' },
  { code: 'text', label: 'Texte' },
  { code: 'logo', label: "Logo d'extension" },
  { code: 'image', label: 'Image' },
  { code: 'card', label: 'Carte' },
] as const

const bgKinds = [
  { code: 'color', label: 'Couleur' },
  { code: 'image', label: 'Image' },
  { code: 'card', label: 'Carte' },
] as const

const textWeightOptions = [
  { code: 'bold', label: 'Gras' },
  { code: 'normal', label: 'Normal' },
] as const

const logoVisualOptions = [
  { code: 'logo', label: 'Logo' },
  { code: 'symbol', label: 'Symbole' },
] as const

const numberOptions = [
  { code: 'on', label: 'Affichés' },
  { code: 'off', label: 'Masqués' },
] as const

const styleLabels = BINDER_STYLES.map((s) => ({ code: s.code, label: s.label }))
const gridOptions = PAGE_GRIDS.map((g) => ({ code: g.code, label: `${g.cols}×${g.rows}` }))
const pageColorOptions = PAGE_COLORS.map((p) => ({ code: p.code, label: p.label }))
const ringCountOptions = RING_COUNTS.map((n) => ({ code: String(n), label: String(n) }))
const binderColorSwatches = BINDER_COLORS.map((c) => c.hex)
const bgColorSwatches = [...BG_COLORS]
const textColorSwatches = [...TEXT_COLORS]

const { updateBinder, uploadCoverImage } = useBinders()
const toast = useToast()

const style = ref(binderStyle(props.initialStyle))
const color = ref<string | null>(props.initialColor)
const coverIds = ref<number[]>([...props.initialCoverIds])
const grid = ref(pageGrid(props.initialGrid).code)
const design = ref<BinderDesign>(binderDesign(props.initialDesign))
const layout = ref<CoverLayout>(coverLayout(props.initialLayout))
const urls = ref<Record<string, string>>({ ...props.initialUrls })
const preview = ref<'ferme' | 'ouvert'>('ferme')
const zone = ref<ZoneKey>('mc')
const logoQ = ref('')
const busy = ref(false)
const saving = ref(false)
const fileInputEl = ref<HTMLInputElement | null>(null)
const uploadTarget = ref<'bg' | ZoneKey>('bg')

const MAX_UPLOAD_BYTES = 3 * 1024 * 1024

const colorHex = computed(() => binderColorHex(color.value))
const coverIdsStr = computed(() => coverIds.value.map(String))
const coverRender = computed(() => renderCover(layout.value, coverImageResolver(urls.value), cardUrl))
const isCustom = computed(() => style.value === 'custom')
const maxCovers = computed(() => binderStyleCovers(style.value))
const el = computed(() => layout.value.zones[zone.value] ?? null)
const kind = computed(() => (el.value?.type ?? 'none') as (typeof elementKinds)[number]['code'])

const gridDef = computed(() => pageGrid(grid.value))
const sheet = computed(() => SHEETS[design.value.pageColor])
const ringPos = computed(() => ringPositions(design.value.ringCount))
const ringColor = computed(() => ringHex(design.value.ringFinish))
const textureClass = computed(() => coverTextureClass(design.value.coverTexture))
const sheen = computed(() => pocketSheen(design.value.pocketFinish))
const sampleCards = computed(() => props.cards.slice(0, pocketsPerPage(gridDef.value)))

const chosen = computed(() =>
  coverIdsStr.value
    .map((id) => props.cards.find((c) => c.id === id))
    .filter((c): c is EditorCard => c != null && !!c.image_url),
)
const previewCovers = computed(() => {
  const source = chosen.value.length > 0 ? chosen.value : props.cards.filter((c) => c.image_url)
  return source.slice(0, Math.max(maxCovers.value, 1)).map((c) => ({ image_url: c.image_url }))
})

const elText = ref('')
watch(
  el,
  (v) => {
    elText.value = v?.type === 'text' ? v.text : ''
  },
  { immediate: true },
)

function normalize(s: string): string {
  return s
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
}

const logoResults = computed(() => {
  const needle = normalize(logoQ.value.trim())
  const list = needle
    ? props.sets.filter((s) => normalize(`${s.name} ${s.serie} ${s.id}`).includes(needle))
    : props.sets
  return list.slice(0, 24)
})

const logoVisualMode = computed(() => {
  if (el.value?.type !== 'logo') return 'logo'
  const s = props.sets.find((x) => x.id === el.value!.setId)
  return s?.symbol === el.value.url ? 'symbol' : 'logo'
})

function cardUrl(id: string): string | null {
  return props.cards.find((c) => c.id === id)?.image_url ?? null
}

function setD(patch: Partial<BinderDesign>): void {
  design.value = { ...design.value, ...patch }
}

function setBg(patch: Partial<CoverLayout['bg']>): void {
  layout.value = { ...layout.value, bg: { ...layout.value.bg, ...patch } }
}

function setZoneEl(key: ZoneKey, next: CoverElement | null): void {
  const zones = { ...layout.value.zones }
  if (next) {
    zones[key] = next
    layout.value = { ...layout.value, zones }
    return
  }
  const { [key]: _drop, ...rest } = zones
  layout.value = { ...layout.value, zones: rest }
}

function onStylePick(code: string): void {
  style.value = binderStyle(code)
  coverIds.value = coverIds.value.slice(0, binderStyleCovers(code))
}

function onSpineColorPick(hex: string | null): void {
  if (hex == null) {
    color.value = null
    return
  }
  color.value = BINDER_COLORS.find((c) => c.hex === hex)?.code ?? null
}

function onBgKindPick(k: string): void {
  if (k === 'image') {
    if (layout.value.bg.image) setBg({ kind: 'image' })
    else pickUpload('bg')
  } else if (k === 'card') {
    const c = props.cards[0]
    if (!c) {
      toast.add({ title: "Range d'abord des cartes dans le classeur", color: 'error' })
      return
    }
    setBg({ kind: 'card', card: layout.value.bg.card ?? c.id })
  } else {
    setBg({ kind: 'color' })
  }
}

function setKind(k: string): void {
  if (k === 'none') {
    clearZone()
    return
  }
  if (k === kind.value) return
  if (k === 'text') {
    setZoneEl(zone.value, {
      type: 'text',
      text: props.name,
      size: 'md',
      weight: 'bold',
      color: '#ffffff',
      font: 'display',
    })
  } else if (k === 'logo') {
    const s = props.sets[0]
    if (!s) {
      toast.add({ title: "Catalogue d'extensions indisponible", color: 'error' })
      return
    }
    const url = logoAssetUrl(s, 'logo')
    if (!url) {
      toast.add({ title: 'Pas de logo pour cette extension', color: 'error' })
      return
    }
    setZoneEl(zone.value, { type: 'logo', setId: s.id, setName: s.name, url, size: 'md' })
  } else if (k === 'card') {
    const c = props.cards[0]
    if (!c) {
      toast.add({ title: "Range d'abord des cartes dans le classeur", color: 'error' })
      return
    }
    setZoneEl(zone.value, { type: 'card', itemId: c.id, size: 'md' })
  } else {
    pickUpload(zone.value)
  }
}

function toggleCover(id: string): void {
  const num = Number(id)
  if (Number.isNaN(num)) return
  const prev = coverIds.value
  if (prev.includes(num)) {
    coverIds.value = prev.filter((x) => x !== num)
    return
  }
  if (prev.length >= maxCovers.value) return
  coverIds.value = [...prev, num]
}

function coverOrder(id: string): number | null {
  const i = coverIdsStr.value.indexOf(id)
  return i === -1 ? null : i
}

function pickUpload(target: 'bg' | ZoneKey): void {
  uploadTarget.value = target
  fileInputEl.value?.click()
}

function logoAssetUrl(s: EditorSet, mode: 'logo' | 'symbol'): string | null {
  const raw = mode === 'symbol' ? s.symbol : s.logo
  if (!raw?.trim()) return s.symbol?.trim() || s.logo?.trim() || null
  const t = raw.trim()
  if (t.startsWith('https://assets.tcgdex.net/')) return t
  if (t.startsWith('https://')) return t
  return null
}

function setThumb(s: EditorSet): string | undefined {
  const cands = catalogLogoCandidates(s.logo ?? undefined, s.symbol ?? undefined)
  return cands[0]
}

function pickLogoSet(s: EditorSet): void {
  if (el.value?.type !== 'logo') return
  const url = logoAssetUrl(s, 'logo') ?? logoAssetUrl(s, 'symbol')
  if (!url) {
    toast.add({ title: 'Pas de visuel pour cette extension', color: 'error' })
    return
  }
  setZoneEl(zone.value, { ...el.value, setId: s.id, setName: s.name, url })
}

function onLogoVisualPick(v: string): void {
  if (el.value?.type !== 'logo') return
  const s = props.sets.find((x) => x.id === el.value!.setId)
  if (!s) return
  const url = logoAssetUrl(s, v === 'symbol' ? 'symbol' : 'logo')
  if (!url) {
    toast.add({ title: 'Pas de visuel de ce type pour cette extension', color: 'error' })
    return
  }
  setZoneEl(zone.value, { ...el.value, url })
}

function patchEl(patch: Partial<CoverElement>): void {
  const cur = el.value
  if (!cur) return
  setZoneEl(zone.value, { ...cur, ...patch } as CoverElement)
}

function patchText(): void {
  if (el.value?.type !== 'text') return
  setZoneEl(zone.value, { ...el.value, text: elText.value })
}

function clearZone(): void {
  setZoneEl(zone.value, null)
}

function clearBgImage(): void {
  setBg({ kind: 'color', image: null })
}

async function upload(file: File): Promise<{ path: string; url: string } | null> {
  if (file.size > MAX_UPLOAD_BYTES) {
    toast.add({ title: 'Image trop lourde (max 3 Mo)', color: 'error' })
    return null
  }
  busy.value = true
  try {
    const res = await uploadCoverImage(props.binderId, file)
    urls.value = { ...urls.value, [res.path]: res.url }
    return res
  } catch (e) {
    toast.add({ title: 'Envoi impossible', description: apiErrorMessage(e), color: 'error' })
    return null
  } finally {
    busy.value = false
    if (fileInputEl.value) fileInputEl.value.value = ''
  }
}

async function onFileInput(ev: Event): Promise<void> {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const target = uploadTarget.value
  const up = await upload(file)
  if (!up) return
  if (target === 'bg') setBg({ kind: 'image', image: up.path })
  else setZoneEl(target, { type: 'image', path: up.path, size: 'md', shape: 'square' })
}

async function save(): Promise<void> {
  saving.value = true
  try {
    await updateBinder(props.binderId, {
      style: style.value,
      color: color.value,
      page_grid: grid.value,
      design: design.value,
      cover: layout.value,
      cover_collection_card_ids: coverIds.value,
    })
    emit('saved')
  } catch (e) {
    toast.add({ title: 'Enregistrement impossible', description: apiErrorMessage(e), color: 'error' })
  } finally {
    saving.value = false
  }
}
</script>
