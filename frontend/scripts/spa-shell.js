// Post-build: derive an empty SPA shell (dist/app.html) from the prerendered
// dist/index.html. nginx serves this for non-prerendered routes (/product/:id,
// /category/:cat) instead of falling back to index.html — otherwise those URLs
// would paint the prerendered HOME page for a frame before the router swaps in
// the real view. The shell keeps the <head> (hashed asset tags, fonts) but has
// an empty <div id="app">, so the app just boots into the requested route.
import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const dist = resolve(process.cwd(), 'dist')
const html = readFileSync(resolve(dist, 'index.html'), 'utf8')

const start = html.indexOf('<div id="app"')
const bodyEnd = html.indexOf('</body>')
if (start === -1 || bodyEnd === -1) {
  console.error('[spa-shell] could not locate #app / </body> in index.html — leaving fallback as-is')
  process.exit(1)
}

const shell = `${html.slice(0, start)}<div id="app"></div>${html.slice(bodyEnd)}`
writeFileSync(resolve(dist, 'app.html'), shell)
console.log('[spa-shell] wrote dist/app.html (empty shell for non-prerendered routes)')
