/* eslint-disable */
// @ts-nocheck
/**
 * Worker de DÉTECTION de carte : un réseau de coins entraîné (MobileNetV3 →
 * 4 coins + présence, dataset synthétique cartes TCGdex en perspective sur
 * fonds réels avec doigts/ombres/reflets) remplace l'ancien pipeline contours
 * OpenCV + suivi de points + fenêtres de recherche aveugles — qui ne cadrait
 * la carte qu'approximativement et accrochait n'importe quel rectangle.
 * Chaque frame donne les coins PRÉCIS de la carte → le cadre suit la carte
 * en continu et le crop d'identification est un warp perspective exact.
 *
 * Protocol (main ⇄ worker):
 *   → { t:'init', ortUrl, wasmBase, cornerModelUrl }   ← { t:'ready' } | { t:'error', m }
 *   → { t:'detect', buf, w, h, vw, vh, im }            ← { t:'quad', corners } | { t:'nq' }
 *                                                        (+ { t:'idcrop', bufs } si `im`)
 * `corners` are always VIDEO-intrinsic pixel coords (TL, TR, BR, BL).
 */

const NET_EDGE = 224
const CROP_EDGE = 256
/**
 * Échelles des crops d'identification, en fraction du bbox de la carte
 * détectée. L'espace d'embedding est très sensible au cadrage (~4 % d'écart
 * coûtent ~0.1 de cosinus) et son optimum mesuré est un crop INTÉRIEUR de la
 * carte (~0.55-0.65 de sa hauteur) : la batterie balaie ce voisinage, ancrée
 * sur la carte réelle — l'identifieur garde le meilleur crop. Réduit à DEUX
 * échelles (le cadre letterbox est précis) : moitié moins d'inférences par
 * tentative, donc identification bien plus rapide sur téléphone.
 */
const ID_CROP_SCALES = [0.6, 0.48]
/** Carte REDRESSÉE (warp perspective du quad) envoyée au matcher pHash — aspect 63:88. */
const PHASH_CARD_W = 180
const PHASH_CARD_H = 252
/**
 * Repli « zone-guide centrale » : après tant de frames SANS quad valide (doigt
 * sur un coin, reflet de pochette/toploader qui casse la détection), on envoie
 * quand même la région centrale au format carte au matcher pHash — la carte est
 * centrée (consigne UI), donc l'empreinte matche souvent là où la détection
 * échoue. Idée reprise du scanner de TailTCG (repli sur le cadre-guide).
 */
const FALLBACK_AFTER = 6
const GUIDE_H_FRAC = 0.62
const CARD_ASPECT = 63 / 88
/** Jitter de position alterné d'une tentative à l'autre (fraction du bbox). */
const ID_CROP_JITTER = [
  { dx: 0, dy: 0 },
  { dx: -0.04, dy: 0 },
  { dx: 0.04, dy: 0 },
  { dx: 0, dy: -0.04 },
  { dx: 0, dy: 0.04 },
]
/**
 * Sigmoïde de présence sous laquelle la frame est déclarée sans carte. La
 * tête de présence est prudente hors distribution (gros plans, sleeves) :
 * seuil bas + validation GÉOMÉTRIQUE du quad (le signal robuste du réseau).
 */
const PRESENCE_MIN = 0.5
/** Cadence max des crops d'identification (l'inférence aval est plus lourde). */
const ID_CROP_MIN_INTERVAL_MS = 300
/**
 * Netteté minimale (variance de Laplacien du crop) pour lancer l'identification.
 * Quand la carte bouge/tremble, les crops sont flous → embedding dégradé →
 * l'ID échoue ou se trompe. On saute alors l'ID (le CADRE continue de suivre)
 * et on attend une frame nette : c'est ce qui rend le scan robuste au mouvement.
 * Calibré sur la vidéo réelle : cartes nettes ~300-400, très floues <150. Seuil
 * bas (130) : l'agrégation temporelle côté page gère déjà le bruit des
 * frames moyennes (les faux ne s'accumulent pas) — le gate n'écarte que le
 * flou franc où l'embedding est inexploitable.
 */
const ID_SHARPNESS_MIN = 130

/** Normalisation ImageNet du détecteur — identique à l'entraînement. */
const IMAGENET_MEAN = [0.485, 0.456, 0.406]
const IMAGENET_STD = [0.229, 0.224, 0.225]

let session = null
let ortRef = null
let lastIdCropAt = 0
let idJitterCursor = 0
/** Frames consécutives sans quad valide (déclenche le repli zone-guide). */
let missCount = 0

/**
 * Le quad prédit ressemble-t-il à une carte ? (convexe, aire plausible,
 * ratio de côtés cart-like) — les frames sans carte produisent des quads
 * dégénérés que la seule tête de présence ne filtre pas toujours.
 */
function quadLooksLikeCard(c) {
  const q = [
    { x: c[0], y: c[1] },
    { x: c[2], y: c[3] },
    { x: c[4], y: c[5] },
    { x: c[6], y: c[7] },
  ]
  let area = 0
  let signRef = 0
  for (let i = 0; i < 4; i += 1) {
    const a = q[i]
    const b = q[(i + 1) % 4]
    const d = q[(i + 2) % 4]
    area += a.x * b.y - b.x * a.y
    const cross = (b.x - a.x) * (d.y - b.y) - (b.y - a.y) * (d.x - b.x)
    const sign = cross >= 0 ? 1 : -1
    if (signRef === 0) {
      signRef = sign
    } else if (sign !== signRef) {
      return false
    }
  }
  area = Math.abs(area) / 2
  // Plafond d'aire : une carte tenue occupe une fraction de l'image ; un quad
  // qui remplit l'écran = le détecteur a accroché le décor (écran d'ordi, mur)
  // quand la carte est loin/absente — on le refuse (retour terrain de Léo).
  if (area < 0.03 || area > 0.5) {
    return false
  }
  const wEdge = (Math.hypot(q[1].x - q[0].x, q[1].y - q[0].y) + Math.hypot(q[2].x - q[3].x, q[2].y - q[3].y)) / 2
  const hEdge = (Math.hypot(q[3].x - q[0].x, q[3].y - q[0].y) + Math.hypot(q[2].x - q[1].x, q[2].y - q[1].y)) / 2
  const long = Math.max(wEdge, hEdge)
  const short = Math.max(1e-6, Math.min(wEdge, hEdge))
  const ratio = long / short
  return ratio >= 1.05 && ratio <= 2.2
}

/** Crop rectangulaire bilinéaire (sous-rect → dst×dst, distorsion carrée). */
function cropRgba(rgba, w, h, rx, ry, rw, rh, dst) {
  const out = new Uint8ClampedArray(dst * dst * 4)
  for (let y = 0; y < dst; y += 1) {
    const sy = Math.max(0, Math.min(h - 1.001, ry + ((y + 0.5) / dst) * rh))
    const y0 = Math.floor(sy)
    const fy = sy - y0
    for (let x = 0; x < dst; x += 1) {
      const sx = Math.max(0, Math.min(w - 1.001, rx + ((x + 0.5) / dst) * rw))
      const x0 = Math.floor(sx)
      const fx = sx - x0
      const p00 = (y0 * w + x0) * 4
      const p10 = p00 + 4
      const p01 = p00 + w * 4
      const p11 = p01 + 4
      const o = (y * dst + x) * 4
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

/**
 * Redresse le quad (TL,TR,BR,BL, coords frame) en un rectangle dstW×dstH par
 * interpolation bilinéaire de quad — la carte devient droite et pleine cadre,
 * entrée idéale de la pHash (qui suppose un cadrage exact).
 */
function warpQuadToRect(rgba, w, h, quad, dstW, dstH) {
  const out = new Uint8ClampedArray(dstW * dstH * 4)
  const tl = quad[0]
  const tr = quad[1]
  const br = quad[2]
  const bl = quad[3]
  for (let y = 0; y < dstH; y += 1) {
    const t = (y + 0.5) / dstH
    for (let x = 0; x < dstW; x += 1) {
      const s = (x + 0.5) / dstW
      const sx = tl.x * (1 - s) * (1 - t) + tr.x * s * (1 - t) + br.x * s * t + bl.x * (1 - s) * t
      const sy = tl.y * (1 - s) * (1 - t) + tr.y * s * (1 - t) + br.y * s * t + bl.y * (1 - s) * t
      const cx = Math.max(0, Math.min(w - 1.001, sx))
      const cy = Math.max(0, Math.min(h - 1.001, sy))
      const x0 = cx | 0
      const y0 = cy | 0
      const fx = cx - x0
      const fy = cy - y0
      const p00 = (y0 * w + x0) * 4
      const p10 = p00 + 4
      const p01 = p00 + w * 4
      const p11 = p01 + 4
      const o = (y * dstW + x) * 4
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

/** Variance du Laplacien 4-voisins d'un crop RGBA (mesure de netteté). */
function sharpness(rgba, dst) {
  let sum = 0
  let sumSq = 0
  let n = 0
  for (let y = 1; y < dst - 1; y += 1) {
    for (let x = 1; x < dst - 1; x += 1) {
      const i = (y * dst + x) * 4
      const c = rgba[i] * 0.299 + rgba[i + 1] * 0.587 + rgba[i + 2] * 0.114
      const up = rgba[i - dst * 4] * 0.299 + rgba[i - dst * 4 + 1] * 0.587 + rgba[i - dst * 4 + 2] * 0.114
      const dn = rgba[i + dst * 4] * 0.299 + rgba[i + dst * 4 + 1] * 0.587 + rgba[i + dst * 4 + 2] * 0.114
      const lf = rgba[i - 4] * 0.299 + rgba[i - 4 + 1] * 0.587 + rgba[i - 4 + 2] * 0.114
      const rt = rgba[i + 4] * 0.299 + rgba[i + 4 + 1] * 0.587 + rgba[i + 4 + 2] * 0.114
      const lap = up + dn + lf + rt - 4 * c
      sum += lap
      sumSq += lap * lap
      n += 1
    }
  }
  if (n === 0) {
    return 0
  }
  const mean = sum / n
  return sumSq / n - mean * mean
}

/**
 * Réduit un buffer RGBA (w×h) vers dst×dst en PRÉSERVANT l'aspect (letterbox,
 * bandes grises sur le petit côté). Le réseau est entraîné sur des cartes à
 * l'aspect naturel 63:88 ; étirer la frame portrait en carré l'écrasait
 * (~0.79 au lieu de 1.4), le réseau prédisait alors un quad portrait gonflé en
 * hauteur une fois remis à l'échelle (cadre bien plus grand que la carte).
 */
function letterboxRgba(rgba, w, h, dst, scale, padX, padY, pad) {
  const out = new Uint8ClampedArray(dst * dst * 4)
  for (let y = 0; y < dst; y += 1) {
    const sy = (y - padY) / scale
    const inY = sy >= 0 && sy <= h - 1.001
    const y0 = Math.max(0, Math.floor(sy))
    const fy = sy - y0
    for (let x = 0; x < dst; x += 1) {
      const o = (y * dst + x) * 4
      const sx = (x - padX) / scale
      if (!inY || sx < 0 || sx > w - 1.001) {
        out[o] = pad
        out[o + 1] = pad
        out[o + 2] = pad
        out[o + 3] = 255
        continue
      }
      const x0 = Math.floor(sx)
      const fx = sx - x0
      const p00 = (y0 * w + x0) * 4
      const p10 = p00 + 4
      const p01 = p00 + w * 4
      const p11 = p01 + 4
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

/** Charge onnxruntime (UMD via importScripts) + le détecteur de coins. */
async function init(d) {
  importScripts(d.ortUrl)
  ortRef = self.ort
  ortRef.env.wasm.wasmPaths = d.wasmBase
  ortRef.env.wasm.numThreads = 1
  const resp = await fetch(d.cornerModelUrl)
  if (!resp.ok) {
    throw new Error(`cornernet HTTP ${resp.status}`)
  }
  session = await ortRef.InferenceSession.create(await resp.arrayBuffer(), { executionProviders: ['wasm'] })
}

/** Une frame : détection des coins, puis crop d'identification throttlé. */
async function detect(d) {
  const rgba = new Uint8ClampedArray(d.buf)
  const scale = NET_EDGE / Math.max(d.w, d.h)
  const padX = (NET_EDGE - d.w * scale) / 2
  const padY = (NET_EDGE - d.h * scale) / 2
  const small = letterboxRgba(rgba, d.w, d.h, NET_EDGE, scale, padX, padY, 114)
  const plane = NET_EDGE * NET_EDGE
  const input = new Float32Array(3 * plane)
  for (let i = 0, p = 0; i < plane; i += 1, p += 4) {
    input[i] = (small[p] / 255 - IMAGENET_MEAN[0]) / IMAGENET_STD[0]
    input[plane + i] = (small[p + 1] / 255 - IMAGENET_MEAN[1]) / IMAGENET_STD[1]
    input[2 * plane + i] = (small[p + 2] / 255 - IMAGENET_MEAN[2]) / IMAGENET_STD[2]
  }
  const out = await session.run({ input: new ortRef.Tensor('float32', input, [1, 3, NET_EDGE, NET_EDGE]) })
  const corners = out.corners.data
  const presence = 1 / (1 + Math.exp(-out.presence.data[0]))
  if (presence < PRESENCE_MIN || !quadLooksLikeCard(corners)) {
    self.postMessage({ t: 'nq' })
    missCount += 1
    // Repli : détection en échec depuis FALLBACK_AFTER frames (doigt/pochette),
    // on tente la pHash sur la zone-guide centrale, la carte y est déjà.
    if (d.im && missCount >= FALLBACK_AFTER && Date.now() - lastIdCropAt >= ID_CROP_MIN_INTERVAL_MS) {
      lastIdCropAt = Date.now()
      try {
        const gh = d.h * GUIDE_H_FRAC
        const gw = gh * CARD_ASPECT
        const gx = (d.w - gw) / 2
        const gy = (d.h - gh) / 2
        const guideQuad = [
          { x: gx, y: gy },
          { x: gx + gw, y: gy },
          { x: gx + gw, y: gy + gh },
          { x: gx, y: gy + gh },
        ]
        const card = warpQuadToRect(rgba, d.w, d.h, guideQuad, PHASH_CARD_W, PHASH_CARD_H)
        self.postMessage({ t: 'cardcrop', buf: card.buffer, w: PHASH_CARD_W, h: PHASH_CARD_H }, [card.buffer])
      } catch {
        /* repli best-effort */
      }
    }
    return
  }
  missCount = 0
  // coins normalisés (repère letterbox) vers coords frame, pour les crops et
  // le cadre affiché, LÉGÈREMENT resserré (5 %) pour épouser au ras de la carte.
  const frameQuad = []
  const fx = d.vw / d.w
  const fy = d.vh / d.h
  let cx = 0
  let cy = 0
  for (let i = 0; i < 4; i += 1) {
    const qx = (corners[i * 2] * NET_EDGE - padX) / scale
    const qy = (corners[i * 2 + 1] * NET_EDGE - padY) / scale
    frameQuad.push({ x: qx, y: qy })
    cx += qx
    cy += qy
  }
  cx /= 4
  cy /= 4
  const SHRINK = 0.95
  const videoQuad = frameQuad.map((p) => ({ x: (cx + (p.x - cx) * SHRINK) * fx, y: (cy + (p.y - cy) * SHRINK) * fy }))
  self.postMessage({ t: 'quad', corners: videoQuad })
  if (d.im && Date.now() - lastIdCropAt >= ID_CROP_MIN_INTERVAL_MS) {
    lastIdCropAt = Date.now()
    try {
      // pHash : carte redressée pleine, envoyée à CHAQUE frame throttlée (même
      // légèrement floue — la pHash refuse d'elle-même) : plus de tentatives,
      // reconnaissance plus rapide quand un doigt / une pochette gêne la netteté.
      const card = warpQuadToRect(rgba, d.w, d.h, frameQuad, PHASH_CARD_W, PHASH_CARD_H)
      self.postMessage({ t: 'cardcrop', buf: card.buffer, w: PHASH_CARD_W, h: PHASH_CARD_H }, [card.buffer])
      // Embedding : crops intérieurs ancrés, seulement sur frame NETTE (un crop
      // flou casse l'embedding ; le cadre, lui, continue de suivre).
      let bx0 = Infinity
      let by0 = Infinity
      let bx1 = -Infinity
      let by1 = -Infinity
      for (const pt of frameQuad) {
        bx0 = Math.min(bx0, pt.x)
        by0 = Math.min(by0, pt.y)
        bx1 = Math.max(bx1, pt.x)
        by1 = Math.max(by1, pt.y)
      }
      const j = ID_CROP_JITTER[idJitterCursor % ID_CROP_JITTER.length]
      const bw = bx1 - bx0
      const bh = by1 - by0
      const cx = bx0 + bw / 2 + j.dx * bw
      const cy = by0 + bh / 2 + j.dy * bh
      const bufs = []
      const midK = ID_CROP_SCALES[Math.floor(ID_CROP_SCALES.length / 2)]
      for (const k of ID_CROP_SCALES) {
        const sw = bw * k
        const sh = bh * k
        const crop = cropRgba(rgba, d.w, d.h, cx - sw / 2, cy - sh / 2, sw, sh, CROP_EDGE)
        bufs.push({ buf: crop.buffer, isMid: k === midK })
      }
      const mid = bufs.find((b) => b.isMid) || bufs[0]
      if (sharpness(new Uint8ClampedArray(mid.buf), CROP_EDGE) >= ID_SHARPNESS_MIN) {
        idJitterCursor += 1
        const out = bufs.map((b) => b.buf)
        self.postMessage({ t: 'idcrop', bufs: out }, out)
      }
    } catch {
      /* crop best-effort — la détection continue */
    }
  }
}

self.onmessage = (e) => {
  const d = e.data
  if (d.t === 'init') {
    init(d)
      .then(() => self.postMessage({ t: 'ready' }))
      .catch((err) => self.postMessage({ t: 'error', m: String((err && err.message) || err) }))
    return
  }
  if (d.t === 'detect') {
    detect(d).catch(() => self.postMessage({ t: 'nq' }))
  }
}
