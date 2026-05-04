#!/usr/bin/env node
/**
 * Copie `api/dist/goupix-amazon-worker(.exe)` vers le nom attendu par Tauri :
 * `web/src-tauri/binaries/goupix-amazon-worker-<rustc-host-triple>(.exe)`
 *
 * PyInstaller sort toujours `goupix-amazon-worker` sans triple ; sans cette étape,
 * le bundle Tauri garde un ancien sidecar → POST /amazon/open-login → 404.
 */

import { execSync } from 'node:child_process'
import { copyFileSync, existsSync, mkdirSync, statSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import process from 'node:process'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

/**
 *
 */
function rustHostTriple() {
  try {
    const out = execSync('rustc -vV', { encoding: 'utf8' })
    const m = out.match(/^host:\s*(\S+)/m)
    if (m) return m[1]
  } catch {
    /* */
  }
  if (process.platform === 'win32') return 'x86_64-pc-windows-msvc'
  if (process.platform === 'darwin') {
    return process.arch === 'arm64' ? 'aarch64-apple-darwin' : 'x86_64-apple-darwin'
  }
  return process.arch === 'arm64' ? 'aarch64-unknown-linux-gnu' : 'x86_64-unknown-linux-gnu'
}

const triple = rustHostTriple()
const repoRoot = resolve(__dirname, '..', '..')
const ext = triple.includes('windows') ? '.exe' : ''
const src = resolve(repoRoot, 'api', 'dist', `goupix-amazon-worker${ext}`)
const binDir = resolve(__dirname, '..', 'src-tauri', 'binaries')
const dest = resolve(binDir, `goupix-amazon-worker-${triple}${ext}`)

if (!existsSync(src)) {
  console.error(`[sync-amazon-worker] introuvable : ${src}`)
  console.error('  Lancez depuis api/ : pyinstaller desktop_amazon_server.spec --noconfirm --clean')
  process.exit(1)
}

const sz = statSync(src).size
if (sz < 512) {
  console.error(`[sync-amazon-worker] fichier trop petit (${sz} o) : ${src}`)
  process.exit(1)
}

mkdirSync(binDir, { recursive: true })
copyFileSync(src, dest)
console.log(`[sync-amazon-worker] copié vers ${dest} (${sz} o, triple=${triple})`)
