/* eslint-disable */
// @ts-nocheck
/**
 * Worker d'identification visuelle DOUBLE ESPACE, hors du main thread (une
 * tentative de 5-6 crops coûte ~1 s d'inférence sur téléphone — sur le main
 * thread elle gelait toute l'interface).
 *
 * Deux embeddings complémentaires, mesurés sur vidéo + captures terrain :
 *  - v3 MobileCLIP-S0 512-d brut : robuste à la lumière naturelle et aux
 *    variantes foil (Caninos reverse holo en plein soleil : 0.74 en tête là
 *    où MobileNet tombait à 0.39), mais regroupe les cartes JA par STYLE de
 *    cadre plus que par artwork → cluster serré indécidable sur une JA
 *    absente de l'index ;
 *  - v2 MobileNetV2-ImageNet PCA-128 : très fidèle à l'artwork exact (la JA
 *    Capidextre → print occidental me02-107 à 0.78 avec marge nette), mais
 *    fragile photométriquement.
 * Chaque espace applique SA politique stricte (plancher + marge face au
 * premier print différent). S0 décide seul ; v2 n'est consulté QUE dans la
 * signature exacte du trou qu'il bouche — top-1 S0 japonais, fort (≥ plancher)
 * mais sans marge (cluster de style JA indécidable) — car sa fragilité
 * photométrique le fait décider à tort ailleurs (mesuré : faux ex1-62 à
 * 0.627/m0.104 sur un crop terrain que S0 tranche correctement).
 *
 * Messages entrants :
 *  - { t:'init', ortUrl, wasmBase, s0ModelUrl, s0BinUrl, s0JsonUrl,
 *      mnetModelUrl, mnetBinUrl, mnetPcaUrl, mnetJsonUrl }
 *  - { t:'identify', seq, bufs: ArrayBuffer[] (RGBA 256×256), language }
 * Messages sortants :
 *  - { t:'ready' } | { t:'init-error', message }
 *  - { t:'result', seq, result: ScanIdentifyResult }
 */

const S0_DIM = 512
const S0_EDGE = 256
const MNET_RAW_DIM = 1280
const MNET_EDGE = 224

// Politiques calibrées indépendamment (rejeu vidéo + captures terrain).
const S0_MIN_SIM = 0.65
const S0_MIN_MARGIN = 0.04
const MNET_MIN_SIM = 0.6
const MNET_MIN_MARGIN = 0.055

/** Normalisation ImageNet du modèle v2 — identique au builder Python v2. */
const IMAGENET_MEAN = [0.485, 0.456, 0.406]
const IMAGENET_STD = [0.229, 0.224, 0.225]

const NONE_RESULT = { decision: null, topCardId: null, topSim: 0, topMargin: 0, bestCropIndex: 0 }

let engine = null

/** Décode un fichier index GPXE → { cards, vectors int8, scales f32, dim }. */
function parseIndex(binBuf, meta) {
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
  const cards = meta.cards.map(([tcgdexCardId, locale, name, setId, localId]) => ({
    tcgdexCardId,
    locale,
    name,
    setId,
    localId,
  }))
  return { cards, vectors, scales, dim }
}

/** Charge onnxruntime (UMD via importScripts) + les 2 modèles + les 2 index. */
async function init(d) {
  importScripts(d.ortUrl)
  const ort = self.ort
  ort.env.wasm.wasmPaths = d.wasmBase
  ort.env.wasm.numThreads = 1

  const urls = [d.s0ModelUrl, d.s0BinUrl, d.s0JsonUrl, d.mnetModelUrl, d.mnetBinUrl, d.mnetPcaUrl, d.mnetJsonUrl]
  const responses = await Promise.all(urls.map((u) => fetch(u)))
  const bad = responses.find((r) => !r.ok)
  if (bad) {
    throw new Error(`scan-embed HTTP ${bad.status} sur ${bad.url}`)
  }
  const [s0Model, s0Bin, s0Json, mnetModel, mnetBin, mnetPca, mnetJson] = await Promise.all([
    responses[0].arrayBuffer(),
    responses[1].arrayBuffer(),
    responses[2].json(),
    responses[3].arrayBuffer(),
    responses[4].arrayBuffer(),
    responses[5].arrayBuffer(),
    responses[6].json(),
  ])

  const s0Index = parseIndex(s0Bin, s0Json)
  const mnetIndex = parseIndex(mnetBin, mnetJson)
  const mnetPcaMean = new Float32Array(mnetPca, 0, MNET_RAW_DIM)
  const mnetPcaComponents = new Float32Array(mnetPca, MNET_RAW_DIM * 4, MNET_RAW_DIM * mnetIndex.dim)
  const s0Session = await ort.InferenceSession.create(s0Model, { executionProviders: ['wasm'] })
  const mnetSession = await ort.InferenceSession.create(mnetModel, { executionProviders: ['wasm'] })
  engine = { ort, s0Session, mnetSession, s0Index, mnetIndex, mnetPcaMean, mnetPcaComponents }
}

/** Réduit un crop RGBA 256×256 en 224×224 (bilinéaire) pour le modèle v2. */
function downscaleRgba(rgba) {
  const out = new Uint8ClampedArray(MNET_EDGE * MNET_EDGE * 4)
  const ratio = S0_EDGE / MNET_EDGE
  for (let y = 0; y < MNET_EDGE; y += 1) {
    const sy = Math.min(S0_EDGE - 1.001, y * ratio)
    const y0 = Math.floor(sy)
    const fy = sy - y0
    for (let x = 0; x < MNET_EDGE; x += 1) {
      const sx = Math.min(S0_EDGE - 1.001, x * ratio)
      const x0 = Math.floor(sx)
      const fx = sx - x0
      const p00 = (y0 * S0_EDGE + x0) * 4
      const p10 = p00 + 4
      const p01 = p00 + S0_EDGE * 4
      const p11 = p01 + 4
      const o = (y * MNET_EDGE + x) * 4
      for (let c = 0; c < 3; c += 1) {
        const top = rgba[p00 + c] * (1 - fx) + rgba[p10 + c] * fx
        const bot = rgba[p01 + c] * (1 - fx) + rgba[p11 + c] * fx
        out[o + c] = top * (1 - fy) + bot * fy
      }
      out[o + 3] = 255
    }
  }
  return out
}

/** Embedding S0 : pixels bruts [0,1], 512-d normalisé (pas de compression). */
async function embedS0(rgba) {
  const plane = S0_EDGE * S0_EDGE
  const input = new Float32Array(3 * plane)
  for (let i = 0, p = 0; i < plane; i += 1, p += 4) {
    input[i] = rgba[p] / 255
    input[plane + i] = rgba[p + 1] / 255
    input[2 * plane + i] = rgba[p + 2] / 255
  }
  const output = await engine.s0Session.run({
    pixel_values: new engine.ort.Tensor('float32', input, [1, 3, S0_EDGE, S0_EDGE]),
  })
  const emb = Object.values(output)[0].data
  const q = new Float32Array(S0_DIM)
  let norm = 0
  for (let i = 0; i < S0_DIM; i += 1) {
    norm += emb[i] * emb[i]
  }
  norm = Math.sqrt(norm) || 1
  for (let i = 0; i < S0_DIM; i += 1) {
    q[i] = emb[i] / norm
  }
  return q
}

/** Embedding v2 : normalisation ImageNet, 1280-d → PCA-128 renormalisée. */
async function embedMnet(rgba224) {
  const plane = MNET_EDGE * MNET_EDGE
  const input = new Float32Array(3 * plane)
  for (let i = 0, p = 0; i < plane; i += 1, p += 4) {
    input[i] = (rgba224[p] / 255 - IMAGENET_MEAN[0]) / IMAGENET_STD[0]
    input[plane + i] = (rgba224[p + 1] / 255 - IMAGENET_MEAN[1]) / IMAGENET_STD[1]
    input[2 * plane + i] = (rgba224[p + 2] / 255 - IMAGENET_MEAN[2]) / IMAGENET_STD[2]
  }
  const output = await engine.mnetSession.run({
    input: new engine.ort.Tensor('float32', input, [1, 3, MNET_EDGE, MNET_EDGE]),
  })
  const emb = Object.values(output)[0].data
  let norm = 0
  for (let i = 0; i < MNET_RAW_DIM; i += 1) {
    norm += emb[i] * emb[i]
  }
  norm = Math.sqrt(norm) || 1
  const dim = engine.mnetIndex.dim
  const reduced = new Float32Array(dim)
  for (let i = 0; i < MNET_RAW_DIM; i += 1) {
    const centered = emb[i] / norm - engine.mnetPcaMean[i]
    if (centered === 0) {
      continue
    }
    const base = i * dim
    for (let j = 0; j < dim; j += 1) {
      reduced[j] += centered * engine.mnetPcaComponents[base + j]
    }
  }
  let rnorm = 0
  for (let j = 0; j < dim; j += 1) {
    rnorm += reduced[j] * reduced[j]
  }
  rnorm = Math.sqrt(rnorm) || 1
  for (let j = 0; j < dim; j += 1) {
    reduced[j] /= rnorm
  }
  return reduced
}

/** Top-8 d'une requête dans un index int8. */
function searchTop8(index, q) {
  const top = []
  const count = index.cards.length
  const dim = index.dim
  for (let i = 0; i < count; i += 1) {
    const base = i * dim
    let dot = 0
    for (let j = 0; j < dim; j += 1) {
      dot += q[j] * index.vectors[base + j]
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
  return top
}

/**
 * Applique la politique d'un espace : plancher + marge face au premier print
 * DIFFÉRENT (les locales d'un même print partagent le tcgdexCardId), et
 * résout la locale stockée selon la langue de session.
 */
function decideFromTop(index, top, minSim, minMargin, sessionLanguage) {
  const bestHit = top[0]
  if (!bestHit) {
    return { decision: null, topCardId: null, topSim: 0, topMargin: 0 }
  }
  const bestCard = index.cards[bestHit.i]
  const next = top.find((t) => index.cards[t.i].tcgdexCardId !== bestCard.tcgdexCardId)
  const margin = bestHit.sim - (next ? next.sim : 0)
  let chosen = bestCard
  if (sessionLanguage !== 'auto') {
    const localeMatch = top
      .filter((t) => index.cards[t.i].tcgdexCardId === bestCard.tcgdexCardId)
      .map((t) => index.cards[t.i])
      .find((c) => c.locale === sessionLanguage)
    if (localeMatch) {
      chosen = localeMatch
    }
  }
  const confident = bestHit.sim >= minSim && !(next && margin < minMargin)
  return {
    decision: confident
      ? {
          tcgdexCardId: chosen.tcgdexCardId,
          language: sessionLanguage === 'auto' ? chosen.locale : sessionLanguage,
          name: chosen.name,
          setId: chosen.setId,
          localId: chosen.localId,
        }
      : null,
    topCardId: bestCard.tcgdexCardId,
    topSim: bestHit.sim,
    topMargin: margin,
  }
}

/**
 * Identifie une tentative : chaque crop est embarqué dans les DEUX espaces ;
 * le meilleur top-8 de chaque espace décide selon sa politique. Les champs de
 * pilotage (topSim/topCardId/bestCropIndex → focus/lock/recalage) viennent de
 * l'espace S0, le plus stable géométriquement.
 */
async function identify(bufs, sessionLanguage) {
  if (!engine || bufs.length === 0) {
    return NONE_RESULT
  }
  let bestS0 = []
  let bestMnet = []
  let bestCropIndex = 0
  let cropIndex = -1
  for (const buf of bufs) {
    cropIndex += 1
    const rgba = new Uint8ClampedArray(buf)
    if (rgba.length !== S0_EDGE * S0_EDGE * 4) {
      continue
    }
    const qS0 = await embedS0(rgba)
    const topS0 = searchTop8(engine.s0Index, qS0)
    if (topS0.length && (bestS0.length === 0 || topS0[0].sim > bestS0[0].sim)) {
      bestS0 = topS0
      bestCropIndex = cropIndex
    }
    const qMnet = await embedMnet(downscaleRgba(rgba))
    const topMnet = searchTop8(engine.mnetIndex, qMnet)
    if (topMnet.length && (bestMnet.length === 0 || topMnet[0].sim > bestMnet[0].sim)) {
      bestMnet = topMnet
    }
  }
  const s0 = decideFromTop(engine.s0Index, bestS0, S0_MIN_SIM, S0_MIN_MARGIN, sessionLanguage)
  // Cluster JA indécidable : S0 voit une carte japonaise avec force mais ne
  // peut pas la départager (les AR japonaises partagent leur style de cadre,
  // et les prints JA récents manquent à l'index) — seul cas où v2 tranche.
  const s0TopCard = bestS0[0] ? engine.s0Index.cards[bestS0[0].i] : null
  const jaClusterBlocked =
    s0.decision === null && s0TopCard !== null && s0TopCard.locale === 'ja' && s0.topSim >= S0_MIN_SIM
  let decision = s0.decision
  if (!decision && jaClusterBlocked) {
    const mnet = decideFromTop(engine.mnetIndex, bestMnet, MNET_MIN_SIM, MNET_MIN_MARGIN, sessionLanguage)
    decision = mnet.decision
  }
  return {
    decision,
    topCardId: s0.topCardId,
    topSim: s0.topSim,
    topMargin: s0.topMargin,
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
