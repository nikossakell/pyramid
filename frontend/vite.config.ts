import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import { readFileSync } from 'node:fs'

/** Το service worker (src/sw/sw.js) βγαίνει ως dist/sw.js με την έκδοση του build, ώστε κάθε build να ανοίγει νέο cache
 *  του app shell. Δεν είναι στο public/ για να μην αντιγράφεται απείραχτο. */
function serviceWorker(): Plugin {
  const version = `${JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf-8')).version}-${Date.now().toString(36)}`
  const src = fileURLToPath(new URL('./src/sw/sw.js', import.meta.url))
  return {
    name: 'pyramid-service-worker',
    apply: 'build',
    generateBundle() {
      this.emitFile({ type: 'asset', fileName: 'sw.js', source: readFileSync(src, 'utf-8').replaceAll('__SW_VERSION__', version) })
    },
  }
}

export default defineConfig({
  plugins: [vue(), serviceWorker()],
  publicDir: 'public',
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: { outDir: 'dist', sourcemap: false },
})
