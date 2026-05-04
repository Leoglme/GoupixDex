#!/usr/bin/env node
// Creates an empty `web/src-tauri/binaries/goupix-vinted-worker-<triple>(.exe)` file when the
// PyInstaller binary has not been built yet (local dev, no CI artifact).
//
// In dev (`tauri dev`), `lib.rs` does not use the sidecar (`cfg(debug_assertions)` branch),
// but Tauri's build step still checks that files listed in `bundle.externalBin` exist.
// This stub satisfies that check without affecting runtime behavior.

import { execSync } from 'node:child_process'
import { existsSync, mkdirSync, writeFileSync, statSync } from 'node:fs'
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
    // fall through to platform guesses below
  }
  // Coarse fallback when Rust is not on PATH (local dev).
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
  // On Windows, a zero-byte .exe is enough for Tauri's presence check.
  writeFileSync(target, '')
  console.log(`[ensure-vinted-worker-stub] stub written: ${target}`)
} else {
  console.log(`[ensure-vinted-worker-stub] existing binary: ${target}`)
}
