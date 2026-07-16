import { copyFileSync, existsSync, mkdirSync, readdirSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDirectory = dirname(fileURLToPath(import.meta.url))
const source = resolve(scriptDirectory, '../public/animations')
const outputDirectory = process.env.AVATAR_ANIMATION_OUTPUT_DIR
  ? resolve(process.env.AVATAR_ANIMATION_OUTPUT_DIR)
  : resolve(scriptDirectory, '../dist/assets/animations')

if (!existsSync(source)) {
  console.warn(`Avatar animation directory is absent: ${source}`)
  process.exit(0)
}

function copyDirectory(sourceDirectory, destinationDirectory) {
  mkdirSync(destinationDirectory, { recursive: true })
  for (const entry of readdirSync(sourceDirectory, { withFileTypes: true })) {
    const sourcePath = join(sourceDirectory, entry.name)
    const destinationPath = join(destinationDirectory, entry.name)
    if (entry.isDirectory()) copyDirectory(sourcePath, destinationPath)
    else if (entry.isFile()) copyFileSync(sourcePath, destinationPath)
  }
}

copyDirectory(source, outputDirectory)
console.log(`Avatar animations copied to ${outputDirectory}`)
