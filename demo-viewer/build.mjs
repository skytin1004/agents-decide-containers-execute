import { cp, mkdir } from 'node:fs/promises'
import { spawn } from 'node:child_process'
import path from 'node:path'
import process from 'node:process'

const root = process.cwd()
const dist = path.join(root, 'dist')
await mkdir(path.join(dist, 'assets'), { recursive: true })
await Promise.all([
  cp(path.join(root, 'src', 'index.html'), path.join(dist, 'index.html')),
  cp(path.join(root, 'src', 'app.js'), path.join(dist, 'app.js')),
  cp(path.join(root, 'assets'), path.join(dist, 'assets'), { recursive: true }),
])

const cli = path.join(root, 'node_modules', '@tailwindcss', 'cli', 'dist', 'index.mjs')
const child = spawn(process.execPath, [cli, '-i', 'src/input.css', '-o', 'dist/styles.css', '--minify'], {
  cwd: root, stdio: 'inherit',
})
child.on('exit', code => process.exit(code ?? 1))
