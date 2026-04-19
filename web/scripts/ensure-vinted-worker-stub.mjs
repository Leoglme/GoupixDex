#!/usr/bin/env node
// Crée un fichier vide `web/src-tauri/binaries/goupix-vinted-worker-<triple>(.exe)`
// si le binaire PyInstaller n'a pas encore été produit (dev local, pas de CI).
//
// En dev (`tauri dev`), `lib.rs` n'utilise pas le sidecar (branche `cfg(debug_assertions)`),
// mais le build script de Tauri valide la présence des fichiers déclarés dans
// `bundle.externalBin`. Ce stub satisfait cette validation sans impact runtime.

import { execSync } from 'node:child_process'
import { existsSync, mkdirSync, writeFileSync, statSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import process from 'node:process'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

function rustHostTriple() {
  try {
    const out = execSync('rustc -vV', { encoding: 'utf8' })
    const m = out.match(/^host:\s*(\S+)/m)
    if (m) return m[1]
  } catch {
    // fallback ci-dessous
  }
  // Fallback grossier (juste pour le dev sans Rust en PATH).
  if (process.platform === 'win32') return 'x86_64-pc-windows-msvc'
  if (process.platform === 'darwin') {
    return process.arch === 'arm64' ? 'aarch64-apple-darwin' : 'x86_64-apple-darwin'
  }
  return process.arch === 'arm64' ? 'aarch64-unknown-linux-gnu' : 'x86_64-unknown-linux-gnu'
}

const triple = rustHostTriple()
const binDir = resolve(__dirname, '..', 'src-tauri', 'binaries')
const ext = triple.includes('windows') ? '.exe' : ''
const target = resolve(binDir, `goupix-vinted-worker-${triple}${ext}`)

if (!existsSync(binDir)) {
  mkdirSync(binDir, { recursive: true })
}

if (!existsSync(target) || statSync(target).size === 0) {
  // Sur Windows, un .exe de 0 octet est OK pour la validation Tauri.
  writeFileSync(target, '')
  console.log(`[ensure-vinted-worker-stub] stub créé : ${target}`)
} else {
  console.log(`[ensure-vinted-worker-stub] binaire existant : ${target}`)
}
