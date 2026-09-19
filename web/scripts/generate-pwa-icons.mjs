/**
 * Regenerate PWA PNG icons from public/pwa-icon.svg (padding + app background).
 * Run: node scripts/generate-pwa-icons.mjs
 */
import sharp from 'sharp'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')
const src = path.join(root, 'public', 'pwa-icon.svg')

const sizes = [
  ['apple-touch-icon.png', 180],
  ['android-chrome-192x192.png', 192],
  ['android-chrome-512x512.png', 512],
  ['favicon-32x32.png', 32],
  ['favicon-16x16.png', 16],
]

for (const [name, size] of sizes) {
  await sharp(src)
    .resize(size, size)
    .png()
    .toFile(path.join(root, 'public', name))
  console.log(`wrote ${name} (${size}px)`)
}
