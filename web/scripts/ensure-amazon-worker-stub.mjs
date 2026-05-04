#!/usr/bin/env node
// Creates a stub `goupix-amazon-worker-<triple>(.exe)` for `bundle.externalBin` validation
// (same approach as ensure-vinted-worker-stub.mjs).

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
    /* */
  }
  if (process.platform === 'win32') return 'x86_64-pc-windows-msvc'
  if (process.platform === 'darwin') {
    return process.arch === 'arm64' ? 'aarch64-apple-darwin' : 'x86_64-apple-darwin'
  }
  return process.arch === 'arm64' ? 'aarch64-unknown-linux-gnu' : 'x86_64-unknown-linux-gnu'
}

const triple = rustHostTriple()
const binDir = resolve(__dirname, '..', 'src-tauri', 'binaries')
const ext = triple.includes('windows') ? '.exe' : ''
const target = resolve(binDir, `goupix-amazon-worker-${triple}${ext}`)

if (!existsSync(binDir)) {
  mkdirSync(binDir, { recursive: true })
}

if (!existsSync(target) || statSync(target).size === 0) {
  writeFileSync(target, '')
  console.log(`[ensure-amazon-worker-stub] stub written: ${target}`)
} else {
  console.log(`[ensure-amazon-worker-stub] existing binary: ${target}`)
}
