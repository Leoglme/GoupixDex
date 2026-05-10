/**
 * Copy `api/dist/goupix-cardmarket-worker(.exe)` to the name Tauri expects:
 * `web/src-tauri/binaries/goupix-cardmarket-worker-<rustc-host-triple>(.exe)`
 */
import { copyFileSync, existsSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { execSync } from 'node:child_process'
import process from 'node:process'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)
const repoRoot = resolve(__dirname, '..', '..')

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
const ext = triple.includes('windows') ? '.exe' : ''
const src = resolve(repoRoot, 'api', 'dist', `goupix-cardmarket-worker${ext}`)
const binDir = resolve(repoRoot, 'web', 'src-tauri', 'binaries')
const dest = resolve(binDir, `goupix-cardmarket-worker-${triple}${ext}`)

if (!existsSync(src)) {
  console.error(`Missing PyInstaller output: ${src}`)
  process.exit(1)
}
mkdirSync(binDir, { recursive: true })
copyFileSync(src, dest)
console.log(`Copied ${src} -> ${dest}`)
