/**
 * One-shot migration: rename app/components Vue files to GoupixDex-prefixed names and
 * update PascalCase tags across `app/`.
 *
 * Skips files already named `GoupixDex*.vue`.
 * Maps `GoupixFlowAnimation.vue` -> `GoupixDexFlowAnimation.vue`.
 *
 * Run: node web/scripts/migrate-components-goupixdex-prefix.mjs
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const webRoot = path.resolve(__dirname, '..')
const componentsDir = path.join(webRoot, 'app', 'components')
const appDir = path.join(webRoot, 'app')

/**
 * @param {string} basename
 * @returns {string}
 */
function pascalFromFile(basename) {
  const base = basename.replace(/\.vue$/i, '')
  return base
    .split(/[-_.]/g)
    .map((p) => (p.length ? p[0].toUpperCase() + p.slice(1) : ''))
    .join('')
}

/**
 * @param {string} dir
 * @returns {string[]}
 */
function walkVueFiles(dir) {
  /** @type {string[]} */
  const out = []
  if (!fs.existsSync(dir)) {
    return out
  }
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, ent.name)
    if (ent.isDirectory()) {
      out.push(...walkVueFiles(full))
    } else if (ent.isFile() && ent.name.endsWith('.vue')) {
      out.push(full)
    }
  }
  return out
}

/**
 * @param {string} filePath
 * @returns {{ newBasename: string, oldTag: string, newTag: string } | null}
 */
function planRename(filePath) {
  const basename = path.basename(filePath)
  if (basename.startsWith('GoupixDex')) {
    return null
  }
  let newBasename
  if (basename === 'GoupixFlowAnimation.vue') {
    newBasename = 'GoupixDexFlowAnimation.vue'
  } else {
    const stem = basename.replace(/\.vue$/i, '')
    newBasename = `GoupixDex${stem}.vue`
  }
  const oldTag = pascalFromFile(basename)
  const newTag = pascalFromFile(newBasename)
  return { newBasename, oldTag, newTag }
}

/**
 * @param {string} root
 * @param {string[]} extensions
 * @returns {string[]}
 */
function walkFilesByExt(root, extensions) {
  /** @type {string[]} */
  const out = []
  /**
   * @param {string} dir
   */
  function walk(dir) {
    if (!fs.existsSync(dir)) {
      return
    }
    for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, ent.name)
      if (ent.isDirectory()) {
        walk(full)
      } else if (ent.isFile()) {
        const ok = extensions.some((ext) => ent.name.endsWith(ext))
        if (ok) {
          out.push(full)
        }
      }
    }
  }
  walk(root)
  return out
}

const files = walkVueFiles(componentsDir)
/** @type {{ from: string, to: string, oldTag: string, newTag: string }[]} */
const renames = []

for (const filePath of files) {
  const plan = planRename(filePath)
  if (!plan) {
    continue
  }
  const dir = path.dirname(filePath)
  const to = path.join(dir, plan.newBasename)
  if (fs.existsSync(to)) {
    console.warn(`[skip] target exists: ${path.relative(webRoot, to)}`)
    continue
  }
  renames.push({ from: filePath, to, oldTag: plan.oldTag, newTag: plan.newTag })
}

renames.sort((a, b) => b.oldTag.length - a.oldTag.length)

for (const r of renames) {
  fs.renameSync(r.from, r.to)
  console.log(`[rename] ${path.relative(webRoot, r.from)} -> ${path.relative(webRoot, r.to)}`)
}

/**
 * @param {string} content
 * @returns {string}
 */
function replaceTags(content) {
  let out = content
  for (const r of renames) {
    const { oldTag, newTag } = r
    out = out.split(`<${oldTag}`).join(`<${newTag}`)
    out = out.split(`</${oldTag}`).join(`</${newTag}`)
  }
  return out
}

const patchFiles = walkFilesByExt(appDir, ['.vue', '.ts', '.tsx', '.md'])
for (const cur of patchFiles) {
  const raw = fs.readFileSync(cur, 'utf8')
  const next = replaceTags(raw)
  if (next !== raw) {
    fs.writeFileSync(cur, next, 'utf8')
    console.log(`[patch] ${path.relative(webRoot, cur)}`)
  }
}

console.log(`Done. Renamed ${renames.length} component files.`)
