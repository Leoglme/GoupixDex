/* eslint-disable */
// @ts-nocheck
/**
 * Worker d'identification par EMPREINTE PERCEPTUELLE (pHash), hors main thread.
 *
 * Complémentaire de l'embedding neuronal : là où MobileCLIP-S0 encode le STYLE
 * de la carte (et confond donc les cartes japonaises d'un même cadre AR), la
 * pHash encode l'ARTWORK — la bonne carte tombe très bas (~0.05-0.2), les
 * imposteurs restent ≥ 0.3 — et l'index (empreintes DCT « carte entière » +
 * « illustration », 512 bits) couvre 94k cartes 6 langues, y compris les sets
 * JA récents SANS image dans TCGdex. Résultat : reconnaissance INSTANTANÉE
 * (distance de Hamming, aucune inférence) qui REFUSE au lieu de deviner.
 *
 * Portage fidèle de la pHash de TailTCG (même prétraitement des deux côtés).
 * La pHash est très sensible au cadrage : la carte redressée est ré-échantillonnée
 * sous une batterie de transformations affines (zoom/décalage/rotation) et le
 * meilleur alignement gagne pour chaque carte candidate.
 *
 * Protocole :
 *   → { t:'init', binUrl, jsonUrl }        ← { t:'ready' } | { t:'init-error', message }
 *   → { t:'match', seq, buf, w, h, language }  ← { t:'result', seq, result }
 * `buf` = RGBA de la carte REDRESSÉE (le détecteur a warpé le quad en rectangle).
 */

const GW = 96
const GH = 132
const N = 32
const K = 16
const SS = 3
const WHOLE = { left: 0, top: 0, width: 1, height: 1 }
const ART = { left: 0.07, top: 0.11, width: 0.86, height: 0.4 }
const WORDS = 8 // 256 bits / 32
/** Poids de l'illustration (discrimine mieux que le cadre, partagé dans un set). */
const W_ART = 0.6
/** Candidats retenus par la 1ʳᵉ passe (grossière) pour l'alignement fin. */
const SHORTLIST = 250
/** Score au-delà duquel rien n'est proposé (REFUS). */
const T_MATCH = 0.28
/** Une carte d'un AUTRE artwork plus proche que ça du meilleur = ambigu, donc refus. */
const T_MARGIN = 0.055
/**
 * Cartes à moins de ça du meilleur score = MÊME artwork (réimpressions multi-set
 * / multi-langue, ex. Capidextre me02-107 et エテボース M2-092) : on les REGROUPE,
 * ce ne sont pas des rivales. La rivale = la 1ʳᵉ carte d'un artwork DIFFÉRENT.
 */
const REPRINT_EPS = 0.04

const COS = (() => {
  const t = new Float64Array(K * N)
  for (let u = 0; u < K; u += 1) {
    for (let x = 0; x < N; x += 1) t[u * N + x] = Math.cos(((2 * x + 1) * u * Math.PI) / (2 * N))
  }
  return t
})()
const POP = (() => {
  const t = new Uint8Array(256)
  for (let i = 1; i < 256; i += 1) t[i] = (i & 1) + t[i >> 1]
  return t
})()

/** Passe grossière sur tout l'index, puis grille dense sur les candidats. */
const COARSE = [
  { z: 1, dx: 0, dy: 0, rot: 0 },
  { z: 0.94, dx: 0, dy: 0, rot: 0 },
  { z: 1.06, dx: 0, dy: 0, rot: 0 },
  { z: 0.94, dx: 0.03, dy: 0, rot: 0 },
  { z: 0.94, dx: -0.03, dy: 0, rot: 0 },
  { z: 0.94, dx: 0, dy: 0.03, rot: 0 },
  { z: 0.94, dx: 0, dy: -0.03, rot: 0 },
  { z: 0.94, dx: 0, dy: 0, rot: 3 },
  { z: 0.94, dx: 0, dy: 0, rot: -3 },
]
const DENSE = (() => {
  const out = []
  // La carte est déjà redressée par le détecteur, une grille modérée suffit.
  for (const z of [1.1, 1.04, 0.98, 0.92, 0.86]) {
    for (const dx of [-0.03, 0, 0.03]) {
      for (const dy of [-0.03, 0, 0.03]) {
        for (const rot of [-3, 0, 3]) out.push({ z, dx, dy, rot })
      }
    }
  }
  return out
})()

let engine = null

/** Empreinte DCT d'une image N×N grise : bloc K×K basse fréquence vs médiane. */
function phashGray(g) {
  const tmp = new Float64Array(K * N)
  for (let y = 0; y < N; y += 1) {
    for (let u = 0; u < K; u += 1) {
      let s = 0
      for (let x = 0; x < N; x += 1) s += g[y * N + x] * COS[u * N + x]
      tmp[u * N + y] = s
    }
  }
  const F = new Float64Array(K * K)
  for (let u = 0; u < K; u += 1) {
    for (let v = 0; v < K; v += 1) {
      let s = 0
      for (let y = 0; y < N; y += 1) s += tmp[u * N + y] * COS[v * N + y]
      F[u * K + v] = s
    }
  }
  const sorted = Array.from(F.subarray(1)).sort((a, b) => a - b)
  const median = sorted[sorted.length >> 1]
  const bits = new Uint8Array((K * K) / 8)
  for (let i = 1; i < K * K; i += 1) if (F[i] > median) bits[i >> 3] |= 1 << (i & 7)
  return bits
}

/** RGBA (cw×ch) converti en luma GW×GH (ITU-R 601, échantillonnage bilinéaire). */
function cardGray(rgba, cw, ch) {
  const g = new Float32Array(GW * GH)
  const rx = cw / GW
  const ry = ch / GH
  for (let j = 0; j < GH; j += 1) {
    const sy = Math.min(ch - 1.001, (j + 0.5) * ry)
    const y0 = Math.floor(sy)
    const fy = sy - y0
    for (let i = 0; i < GW; i += 1) {
      const sx = Math.min(cw - 1.001, (i + 0.5) * rx)
      const x0 = Math.floor(sx)
      const fx = sx - x0
      const p00 = (y0 * cw + x0) * 4
      const p10 = p00 + 4
      const p01 = p00 + cw * 4
      const p11 = p01 + 4
      const l00 = rgba[p00] * 0.299 + rgba[p00 + 1] * 0.587 + rgba[p00 + 2] * 0.114
      const l10 = rgba[p10] * 0.299 + rgba[p10 + 1] * 0.587 + rgba[p10 + 2] * 0.114
      const l01 = rgba[p01] * 0.299 + rgba[p01 + 1] * 0.587 + rgba[p01 + 2] * 0.114
      const l11 = rgba[p11] * 0.299 + rgba[p11 + 1] * 0.587 + rgba[p11 + 2] * 0.114
      g[j * GW + i] = (l00 * (1 - fx) + l10 * fx) * (1 - fy) + (l01 * (1 - fx) + l11 * fx) * fy
    }
  }
  return g
}

/** Lecture bilinéaire de l'image grise GW×GH, bords répétés. */
function sample(g, x, y) {
  if (x < 0) x = 0
  else if (x > GW - 1.001) x = GW - 1.001
  if (y < 0) y = 0
  else if (y > GH - 1.001) y = GH - 1.001
  const x0 = x | 0
  const y0 = y | 0
  const fx = x - x0
  const fy = y - y0
  const i = y0 * GW + x0
  return (g[i] * (1 - fx) + g[i + 1] * fx) * (1 - fy) + (g[i + GW] * (1 - fx) + g[i + GW + 1] * fx) * fy
}

/** Échantillonne une fenêtre de la carte en N×N sous une transformation affine. */
function grid(g, win, t) {
  const out = new Float32Array(N * N)
  const rad = (t.rot * Math.PI) / 180
  const c = Math.cos(rad)
  const s = Math.sin(rad)
  const cx = GW / 2 + t.dx * GW
  const cy = GH / 2 + t.dy * GH
  for (let j = 0; j < N; j += 1) {
    for (let i = 0; i < N; i += 1) {
      let acc = 0
      for (let b = 0; b < SS; b += 1) {
        for (let a = 0; a < SS; a += 1) {
          const u = win.left + (win.width * (i + (a + 0.5) / SS)) / N
          const v = win.top + (win.height * (j + (b + 0.5) / SS)) / N
          const x = (u - 0.5) * t.z * GW
          const y = (v - 0.5) * t.z * GH
          acc += sample(g, cx + x * c - y * s, cy + x * s + y * c)
        }
      }
      out[j * N + i] = acc / (SS * SS)
    }
  }
  return out
}

/** Les deux empreintes (packées en 8 mots u32) d'une image grise sous transfo. */
function variantWords(g, t) {
  const w = phashGray(grid(g, WHOLE, t))
  const a = phashGray(grid(g, ART, t))
  return { whole: new Uint32Array(w.buffer, 0, WORDS), art: new Uint32Array(a.buffer, 0, WORDS) }
}

/** Distance (0..1) d'une variante à la carte d'index i. */
function distTo(variant, i) {
  const o = i * WORDS
  let dw = 0
  let da = 0
  for (let w = 0; w < WORDS; w += 1) {
    let xw = variant.whole[w] ^ engine.wholes[o + w]
    let xa = variant.art[w] ^ engine.arts[o + w]
    dw += POP[xw & 255] + POP[(xw >>> 8) & 255] + POP[(xw >>> 16) & 255] + POP[(xw >>> 24) & 255]
    da += POP[xa & 255] + POP[(xa >>> 8) & 255] + POP[(xa >>> 16) & 255] + POP[(xa >>> 24) & 255]
  }
  return ((1 - W_ART) * dw + W_ART * da) / 256
}

/** Charge l'index binaire GPXH + les métadonnées. */
async function init(d) {
  const [binResp, jsonResp] = await Promise.all([fetch(d.binUrl), fetch(d.jsonUrl)])
  if (!binResp.ok || !jsonResp.ok) {
    throw new Error(`phash HTTP ${binResp.status}/${jsonResp.status}`)
  }
  const bin = await binResp.arrayBuffer()
  const meta = await jsonResp.json()
  const view = new DataView(bin)
  const magicOk =
    view.getUint8(0) === 0x47 && view.getUint8(1) === 0x50 && view.getUint8(2) === 0x58 && view.getUint8(3) === 0x48
  const count = view.getUint32(8, true)
  if (!magicOk || count !== meta.cards.length) {
    throw new Error('phash: index binaire invalide')
  }
  const wholes = new Uint32Array(count * WORDS)
  const arts = new Uint32Array(count * WORDS)
  for (let i = 0; i < count; i += 1) {
    const base = 16 + i * 64
    for (let w = 0; w < WORDS; w += 1) {
      wholes[i * WORDS + w] = view.getUint32(base + w * 4, true)
      arts[i * WORDS + w] = view.getUint32(base + 32 + w * 4, true)
    }
  }
  const cards = meta.cards.map(([tcgdexCardId, locale, name, setId, localId]) => ({
    tcgdexCardId,
    locale,
    name,
    setId,
    localId,
  }))
  engine = { wholes, arts, cards, count }
}

/**
 * Reconnaît une carte redressée. Deux passes : variantes grossières contre tout
 * l'index pour une shortlist, puis grille dense dessus (meilleur alignement).
 * Regroupe les langues d'une même carte ; refuse si le meilleur est trop loin
 * ou si une AUTRE carte est trop proche (ambigu).
 */
function match(rgba, cw, ch, language) {
  if (!engine) return { status: 'none', decision: null, score: 1 }
  const g = cardGray(rgba, cw, ch)
  const coarse = COARSE.map((t) => variantWords(g, t))
  const best = new Float32Array(engine.count)
  best.fill(2)
  for (let i = 0; i < engine.count; i += 1) {
    let m = 2
    for (let k = 0; k < coarse.length; k += 1) {
      const dd = distTo(coarse[k], i)
      if (dd < m) m = dd
    }
    best[i] = m
  }
  // shortlist
  const idx = Array.from({ length: engine.count }, (_, i) => i)
  idx.sort((a, b) => best[a] - best[b])
  const shortlist = idx.slice(0, SHORTLIST)
  const dense = DENSE.map((t) => variantWords(g, t))
  const scored = shortlist.map((i) => {
    let m = best[i]
    for (let k = 0; k < dense.length; k += 1) {
      const dd = distTo(dense[k], i)
      if (dd < m) m = dd
    }
    return { i, score: m }
  })
  scored.sort((a, b) => a.score - b.score)
  const top = scored[0]
  const topCard = engine.cards[top.i]
  // Rivale = 1re carte d'un AUTRE artwork (score nettement plus haut). Les prints
  // du même artwork (mêmes ~bits, à REPRINT_EPS près) sont regroupés, pas rivaux.
  let rivalScore = 1
  for (let r = 1; r < scored.length; r += 1) {
    if (scored[r].score - top.score > REPRINT_EPS) {
      rivalScore = scored[r].score
      break
    }
  }
  const confident = top.score <= T_MATCH && rivalScore - top.score >= T_MARGIN
  // Langue : si la carte existe dans la langue de session à un score proche, la préférer.
  let chosen = topCard
  if (language && language !== 'auto') {
    for (const s of scored) {
      const c = engine.cards[s.i]
      if (c.locale === language && c.name === topCard.name && s.score - top.score <= 0.03) {
        chosen = c
        break
      }
    }
  }
  return {
    status: confident ? 'match' : 'none',
    decision: confident
      ? {
          tcgdexCardId: chosen.tcgdexCardId,
          language: language && language !== 'auto' ? language : chosen.locale,
          name: chosen.name,
          setId: chosen.setId,
          localId: chosen.localId,
        }
      : null,
    score: top.score,
    rival: rivalScore,
    topName: topCard.name,
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
  if (d.t === 'match') {
    let result
    try {
      result = match(new Uint8ClampedArray(d.buf), d.w, d.h, d.language)
    } catch (err) {
      result = { status: 'none', decision: null, score: 1 }
    }
    self.postMessage({ t: 'result', seq: d.seq, result })
  }
}
