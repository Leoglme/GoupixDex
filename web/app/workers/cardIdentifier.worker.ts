/* eslint-disable */
// @ts-nocheck
/**
 * Worker d'identification visuelle : embedding MobileNet (onnxruntime wasm)
 * + projection PCA + cosinus contre l'index ~44k cartes, le tout HORS du main
 * thread. Sur téléphone, une tentative (5-6 crops) coûte 0,5-1 s d'inférence :
 * exécutée sur le main thread elle gelait toute l'interface (taps ignorés,
 * overlay figé). Ici elle ne bloque que ce worker.
 *
 * Messages entrants :
 *  - { t:'init', ortUrl, wasmBase, modelUrl, indexBinUrl, pcaUrl, indexJsonUrl }
 *  - { t:'identify', seq, bufs: ArrayBuffer[], language }
 * Messages sortants :
 *  - { t:'ready' } | { t:'init-error', message }
 *  - { t:'result', seq, result: ScanIdentifyResult }
 */

const EMBED_DIM = 1280

// Politique de confiance calibrée par rejeu vidéo : plancher DE similarité
// ET marge face au premier print différent, sans exception — un voisin
// d'artwork peut monter à 0.70 sur un bon crop (Oricorio A3-165 face à un
// Capidextre), seule la marge sépare alors le vrai print.
const CONFIDENT_SIMILARITY_MIN = 0.6
const MIN_MARGIN_TO_NEXT_CARD = 0.055

/** Normalisation ImageNet — DOIT rester identique au builder Python. */
const IMAGENET_MEAN = [0.485, 0.456, 0.406]
const IMAGENET_STD = [0.229, 0.224, 0.225]

const NONE_RESULT = { decision: null, topCardId: null, topSim: 0, topMargin: 0, bestCropIndex: 0 }

let index = null

/** Charge onnxruntime (UMD via importScripts) + modèle + index + PCA. */
async function init(d) {
  importScripts(d.ortUrl)
  const ort = self.ort
  ort.env.wasm.wasmPaths = d.wasmBase
  ort.env.wasm.numThreads = 1

  const [modelResp, binResp, pcaResp, jsonResp] = await Promise.all([
    fetch(d.modelUrl),
    fetch(d.indexBinUrl),
    fetch(d.pcaUrl),
    fetch(d.indexJsonUrl),
  ])
  if (!modelResp.ok || !binResp.ok || !pcaResp.ok || !jsonResp.ok) {
    throw new Error(`scan-embed HTTP ${modelResp.status}/${binResp.status}/${pcaResp.status}/${jsonResp.status}`)
  }
  const [modelBuf, binBuf, pcaBuf, meta] = await Promise.all([
    modelResp.arrayBuffer(),
    binResp.arrayBuffer(),
    pcaResp.arrayBuffer(),
    jsonResp.json(),
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
  const vectors = new Int8Array(count * dim)
  const scales = new Float32Array(count)
  for (let i = 0; i < count; i += 1) {
    vectors.set(new Int8Array(binBuf, 16 + i * stride, dim), i * dim)
    scales[i] = view.getFloat32(16 + i * stride + dim, true)
  }

  const pcaMean = new Float32Array(pcaBuf, 0, EMBED_DIM)
  const pcaComponents = new Float32Array(pcaBuf, EMBED_DIM * 4, EMBED_DIM * dim)
  const session = await ort.InferenceSession.create(modelBuf, { executionProviders: ['wasm'] })
  const cards = meta.cards.map(([tcgdexCardId, locale, name, setId, localId]) => ({
    tcgdexCardId,
    locale,
    name,
    setId,
    localId,
  }))
  index = { ort, session, cards, vectors, scales, dim, pcaMean, pcaComponents }
}

/** Embarque un crop 224×224 dans l'espace d'index (embedding → PCA → norme). */
async function embedCrop(rgba) {
  if (rgba.length !== 224 * 224 * 4) {
    return null
  }
  const input = new Float32Array(3 * 224 * 224)
  const plane = 224 * 224
  for (let i = 0, p = 0; i < plane; i += 1, p += 4) {
    input[i] = (rgba[p] / 255 - IMAGENET_MEAN[0]) / IMAGENET_STD[0]
    input[plane + i] = (rgba[p + 1] / 255 - IMAGENET_MEAN[1]) / IMAGENET_STD[1]
    input[2 * plane + i] = (rgba[p + 2] / 255 - IMAGENET_MEAN[2]) / IMAGENET_STD[2]
  }
  const output = await index.session.run({
    input: new index.ort.Tensor('float32', input, [1, 3, 224, 224]),
  })
  const first = Object.values(output)[0]
  if (!first) {
    return null
  }
  const emb = first.data
  let norm = 0
  for (let i = 0; i < EMBED_DIM; i += 1) {
    norm += emb[i] * emb[i]
  }
  norm = Math.sqrt(norm) || 1
  const reduced = new Float32Array(index.dim)
  for (let i = 0; i < EMBED_DIM; i += 1) {
    const centered = emb[i] / norm - index.pcaMean[i]
    if (centered === 0) {
      continue
    }
    const base = i * index.dim
    for (let j = 0; j < index.dim; j += 1) {
      reduced[j] += centered * index.pcaComponents[base + j]
    }
  }
  let rnorm = 0
  for (let j = 0; j < index.dim; j += 1) {
    rnorm += reduced[j] * reduced[j]
  }
  rnorm = Math.sqrt(rnorm) || 1
  for (let j = 0; j < index.dim; j += 1) {
    reduced[j] /= rnorm
  }
  return reduced
}

/**
 * Identifie une tentative (meilleur top-8 sur l'ensemble des crops) et
 * applique la politique de confiance. Voir le JSDoc d'en-tête pour le contrat.
 */
async function identify(bufs, sessionLanguage) {
  if (!index || bufs.length === 0) {
    return NONE_RESULT
  }
  let best = []
  let bestCropIndex = 0
  let cropIndex = -1
  for (const buf of bufs) {
    cropIndex += 1
    const query = await embedCrop(new Uint8ClampedArray(buf))
    if (!query) {
      continue
    }
    const top = []
    const count = index.cards.length
    for (let i = 0; i < count; i += 1) {
      const base = i * index.dim
      let dot = 0
      for (let j = 0; j < index.dim; j += 1) {
        dot += query[j] * index.vectors[base + j]
      }
      const sim = dot * index.scales[i]
      if (top.length < 8 || sim > top[top.length - 1].sim) {
        top.push({ i, sim })
        top.sort((a, b) => b.sim - a.sim)
        if (top.length > 8) {
          top.pop()
        }
      }
    }
    if (top.length && (best.length === 0 || top[0].sim > best[0].sim)) {
      best = top
      bestCropIndex = cropIndex
    }
  }
  const bestHit = best[0]
  if (!bestHit) {
    return NONE_RESULT
  }
  const bestCard = index.cards[bestHit.i]
  // Cluster = les locales du MÊME print (id partagé) ; marge mesurée face au
  // premier print différent (top-8 entièrement même print = domination totale).
  const next = best.find((t) => index.cards[t.i].tcgdexCardId !== bestCard.tcgdexCardId)
  const margin = bestHit.sim - (next ? next.sim : 0)
  let chosen = bestCard
  if (sessionLanguage !== 'auto') {
    const localeMatch = best
      .filter((t) => index.cards[t.i].tcgdexCardId === bestCard.tcgdexCardId)
      .map((t) => index.cards[t.i])
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
  const confident = bestHit.sim >= CONFIDENT_SIMILARITY_MIN && !(next && margin < MIN_MARGIN_TO_NEXT_CARD)
  return {
    decision: confident ? topCandidate : null,
    topCardId: bestCard.tcgdexCardId,
    topSim: bestHit.sim,
    topMargin: margin,
    bestCropIndex,
  }
}

self.onmessage = (e) => {
  const d = e.data
  if (d.t === 'init') {
    init(d)
      .then(() => self.postMessage({ t: 'ready' }))
      .catch((err) => self.postMessage({ t: 'init-error', message: String((err && err.message) || err) }))
    return
  }
  if (d.t === 'identify') {
    identify(d.bufs, d.language)
      .then((result) => self.postMessage({ t: 'result', seq: d.seq, result }))
      .catch(() => self.postMessage({ t: 'result', seq: d.seq, result: NONE_RESULT }))
  }
}
