import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import './styles/base.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')

// Service worker μόνο στο production build: cache του app shell, ποτέ του /api/ (public/sw.js).
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => undefined)
  })
}
