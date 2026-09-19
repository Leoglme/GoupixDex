import type { ComputedRef, Ref } from 'vue'
import type { ScanCardLanguage, ScanIdentifyResult, ScanMatchCard } from '~/types/ScanMatch'

const INDEX_VERSION = 2
const EMBED_DIM = 1280
const MODEL_URL = '/scan-model/mobilenet-embed-int8.onnx'
const ORT_WASM_BASE = '/ort/'

/**
 * Politique de confiance sur les similarités cosinus DANS L'ESPACE PROJETÉ
 * (PCA centrée + renormalisée : les valeurs y sont plus basses que sur les
 * embeddings bruts). Le cluster du sommet se définit par IDENTITÉ de carte
 * (les locales d'un même print partagent le tcgdexCardId) ; la marge s'exige
 * face au premier print DIFFÉRENT. Calibré par rejeu de la vidéo réelle :
 * vrais positifs 0.60-0.75 (fenêtres) ; le bruit de scène plafonne à ≈ 0.58
 * une fois les faux quads filtrés par la forme.
 */
const CONFIDENT_SIMILARITY_MIN = 0.6
const MIN_MARGIN_TO_NEXT_CARD = 0.055
/**
 * Au-dessus de ce plancher, commit SANS exiger de marge : deux artworks
 * réellement différents ne cohabitent jamais à ce niveau — seul le jumeau
 * JA/occidental du même dessin peut coller au top-1, et il porte le même choix.
 */
const HIGH_CONFIDENCE_SIMILARITY = 0.68

/** Normalisation ImageNet — DOIT rester identique au builder Python. */
const IMAGENET_MEAN = [0.485, 0.456, 0.406]
const IMAGENET_STD = [0.229, 0.224, 0.225]

type EmbedIndexData = {
  cards: ScanMatchCard[]
  vectors: Int8Array
  scales: Float32Array
  dim: number
  pcaMean: Float32Array
  pcaComponents: Float32Array
  session: { run: (feeds: Record<string, unknown>) => Promise<Record<string, { data: Float32Array }>> }
  tensorCtor: new (type: string, data: Float32Array, dims: number[]) => unknown
}

let loadPromise: Promise<EmbedIndexData> | null = null

/**
 * Télécharge modèle + index + PCA et initialise ONNX Runtime (une fois par
 * session ; le cache HTTP du navigateur porte les rechargements).
 * @returns {Promise<EmbedIndexData>} Données prêtes pour {@link useScanEmbedIndex}.
 */
async function loadOnce(): Promise<EmbedIndexData> {
  if (!loadPromise) {
    loadPromise = (async () => {
      // Build wasm-only : évite le bundle jsep/webgpu (et ses 28 Mo de wasm).
      const ort = await import('onnxruntime-web/wasm')
      ort.env.wasm.wasmPaths = ORT_WASM_BASE
      ort.env.wasm.numThreads = 1
      const [modelResp, binResp, pcaResp, jsonResp] = await Promise.all([
        fetch(MODEL_URL),
        fetch(`/scan-index/embed-v${INDEX_VERSION}.bin`),
        fetch(`/scan-index/embed-pca-v${INDEX_VERSION}.bin`),
        fetch(`/scan-index/embed-v${INDEX_VERSION}.json`),
      ])
      if (!modelResp.ok || !binResp.ok || !pcaResp.ok || !jsonResp.ok) {
        throw new Error(`scan-embed HTTP ${modelResp.status}/${binResp.status}/${pcaResp.status}/${jsonResp.status}`)
      }
      const [modelBuf, binBuf, pcaBuf, meta] = await Promise.all([
        modelResp.arrayBuffer(),
        binResp.arrayBuffer(),
        pcaResp.arrayBuffer(),
        jsonResp.json() as Promise<{ version: number; dim: number; cards: [string, string, string, string, string][] }>,
      ])

      const view = new DataView(binBuf)
      const magicOk =
        view.getUint8(0) === 0x47 && view.getUint8(1) === 0x50 && view.getUint8(2) === 0x58 && view.getUint8(3) === 0x45
      const count = view.getUint32(8, true)
      const dim = view.getUint32(12, true)
      if (!magicOk || count !== meta.cards.length) {
        throw new Error('scan-embed: index binaire invalide')
      }
      const stride = dim + 4
      const raw = new Uint8Array(binBuf, 16)
      const vectors = new Int8Array(count * dim)
      const scales = new Float32Array(count)
      const scaleView = new DataView(binBuf)
      for (let i = 0; i < count; i += 1) {
        vectors.set(new Int8Array(binBuf, 16 + i * stride, dim), i * dim)
        scales[i] = scaleView.getFloat32(16 + i * stride + dim, true)
      }
      void raw

      const pcaMean = new Float32Array(pcaBuf, 0, EMBED_DIM)
      const pcaComponents = new Float32Array(pcaBuf, EMBED_DIM * 4, EMBED_DIM * dim)

      const session = await ort.InferenceSession.create(modelBuf, { executionProviders: ['wasm'] })
      const cards: ScanMatchCard[] = meta.cards.map(([tcgdexCardId, locale, name, setId, localId]) => ({
        tcgdexCardId,
        locale,
        name,
        setId,
        localId,
      }))
      return {
        cards,
        vectors,
        scales,
        dim,
        pcaMean,
        pcaComponents,
        session: session as unknown as EmbedIndexData['session'],
        tensorCtor: ort.Tensor as unknown as EmbedIndexData['tensorCtor'],
      }
    })()
    loadPromise.catch(() => {
      loadPromise = null
    })
  }
  return loadPromise
}

/**
 * Identification visuelle v2 : embedding MobileNet (tolérant au cadrage, à
 * l'éclairage et aux reflets de sleeve — là où le hash perceptuel v1 exigeait
 * un crop au pixel près) matché en cosinus contre les ~44k images TCGdex.
 * Voir `api/scripts/build_scan_embed_index.py`.
 * @returns {object} État de chargement, `load()` et `identify()`.
 */
export function useScanEmbedIndex() {
  const data: Ref<EmbedIndexData | null> = ref(null)
  const loadFailed: Ref<boolean> = ref(false)
  const ready: ComputedRef<boolean> = computed(() => data.value !== null)

  /**
   * Charge modèle + index (idempotent). Un échec réseau laisse le scanner en
   * mode photo-OCR serveur — jamais bloquant.
   * @returns {Promise<void>} Résolue une fois le chargement terminé (ou l'échec acté).
   */
  async function load(): Promise<void> {
    if (ready.value) {
      return
    }
    try {
      data.value = await loadOnce()
      loadFailed.value = false
    } catch {
      loadFailed.value = true
    }
  }

  /**
   * Embarque un crop 224×224 dans l'espace d'index (embedding → PCA → norme).
   * @param rgba - Pixels RGBA du crop (224×224×4).
   * @param idx - Données d'index chargées.
   * @returns {Promise<Float32Array | null>} Vecteur requête normalisé, ou `null`.
   */
  async function embedCrop(rgba: Uint8ClampedArray, idx: EmbedIndexData): Promise<Float32Array | null> {
    if (rgba.length !== 224 * 224 * 4) {
      return null
    }
    const input = new Float32Array(3 * 224 * 224)
    const plane = 224 * 224
    for (let i = 0, p = 0; i < plane; i += 1, p += 4) {
      input[i] = (rgba[p]! / 255 - IMAGENET_MEAN[0]!) / IMAGENET_STD[0]!
      input[plane + i] = (rgba[p + 1]! / 255 - IMAGENET_MEAN[1]!) / IMAGENET_STD[1]!
      input[2 * plane + i] = (rgba[p + 2]! / 255 - IMAGENET_MEAN[2]!) / IMAGENET_STD[2]!
    }
    const TensorCtor = idx.tensorCtor
    const output = await idx.session.run({ input: new TensorCtor('float32', input, [1, 3, 224, 224]) })
    const first = Object.values(output)[0]
    if (!first) {
      return null
    }
    const emb = first.data
    let norm = 0
    for (let i = 0; i < EMBED_DIM; i += 1) {
      norm += emb[i]! * emb[i]!
    }
    norm = Math.sqrt(norm) || 1
    const reduced = new Float32Array(idx.dim)
    for (let i = 0; i < EMBED_DIM; i += 1) {
      const centered = emb[i]! / norm - idx.pcaMean[i]!
      if (centered === 0) {
        continue
      }
      const base = i * idx.dim
      for (let j = 0; j < idx.dim; j += 1) {
        reduced[j] = reduced[j]! + centered * idx.pcaComponents[base + j]!
      }
    }
    let rnorm = 0
    for (let j = 0; j < idx.dim; j += 1) {
      rnorm += reduced[j]! * reduced[j]!
    }
    rnorm = Math.sqrt(rnorm) || 1
    for (let j = 0; j < idx.dim; j += 1) {
      reduced[j] = reduced[j]! / rnorm
    }
    return reduced
  }

  /**
   * Identifie le meilleur des crops candidats d'une tentative (variantes de
   * cadrage du worker) contre tout l'index, et applique la politique de
   * confiance (plancher + marge face au premier print différent).
   * @param crops - Crops RGBA 224×224 de la tentative (1 à 6).
   * @param sessionLanguage - Langue de session (`auto` = locale du meilleur print).
   * @returns {Promise<ScanIdentifyResult>} Décision sûre éventuelle + meilleur hit brut
   *   (sert à la recherche focalisée, au cadre précoce et au recalage en cooldown).
   */
  async function identify(crops: Uint8ClampedArray[], sessionLanguage: ScanCardLanguage): Promise<ScanIdentifyResult> {
    const none: ScanIdentifyResult = { decision: null, topCardId: null, topSim: 0, topMargin: 0, bestCropIndex: 0 }
    const idx = data.value
    if (!idx || crops.length === 0) {
      return none
    }
    let best: { i: number; sim: number }[] = []
    let bestCropIndex = 0
    let cropIndex = -1
    for (const rgba of crops) {
      cropIndex += 1
      const query = await embedCrop(rgba, idx)
      if (!query) {
        continue
      }
      const top: { i: number; sim: number }[] = []
      const count = idx.cards.length
      for (let i = 0; i < count; i += 1) {
        const base = i * idx.dim
        let dot = 0
        for (let j = 0; j < idx.dim; j += 1) {
          dot += query[j]! * idx.vectors[base + j]!
        }
        const sim = dot * idx.scales[i]!
        if (top.length < 8 || sim > top[top.length - 1]!.sim) {
          top.push({ i, sim })
          top.sort((a, b) => b.sim - a.sim)
          if (top.length > 8) {
            top.pop()
          }
        }
      }
      if (top.length && (best.length === 0 || top[0]!.sim > best[0]!.sim)) {
        best = top
        bestCropIndex = cropIndex
      }
    }
    const bestHit = best[0]
    if (!bestHit) {
      return none
    }
    const bestCard = idx.cards[bestHit.i]!
    // Cluster = les locales du MÊME print (id partagé) ; marge mesurée face au
    // premier print différent (top-8 entièrement même print = domination totale).
    const next = best.find((t) => idx.cards[t.i]!.tcgdexCardId !== bestCard.tcgdexCardId)
    const margin = bestHit.sim - (next ? next.sim : 0)
    let chosen = bestCard
    if (sessionLanguage !== 'auto') {
      const localeMatch = best
        .filter((t) => idx.cards[t.i]!.tcgdexCardId === bestCard.tcgdexCardId)
        .map((t) => idx.cards[t.i]!)
        .find((c) => c.locale === sessionLanguage)
      if (localeMatch) {
        chosen = localeMatch
      }
    }
    const topCandidate = {
      tcgdexCardId: chosen.tcgdexCardId,
      language: sessionLanguage === 'auto' ? chosen.locale : sessionLanguage,
      name: chosen.name,
      setId: chosen.setId,
      localId: chosen.localId,
    }
    // Très haute similarité : seuls le vrai print et ses jumeaux d'artwork
    // (numérotations JA/occidentale du même dessin) vivent là-haut — la marge
    // face à un « print différent » ne discrimine alors plus rien d'utile.
    const dominant = bestHit.sim >= HIGH_CONFIDENCE_SIMILARITY
    const confident =
      dominant || (bestHit.sim >= CONFIDENT_SIMILARITY_MIN && !(next && margin < MIN_MARGIN_TO_NEXT_CARD))
    return {
      decision: confident ? topCandidate : null,
      topCardId: bestCard.tcgdexCardId,
      topSim: bestHit.sim,
      topMargin: margin,
      bestCropIndex,
    }
  }

  return { ready, loadFailed, load, identify }
}
