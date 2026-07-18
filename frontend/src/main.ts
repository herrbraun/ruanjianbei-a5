import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { setUnauthorizedHandler } from './api/http'
import router from './router'
import { useAuthStore } from './stores/auth'
import './styles.css'
import './a-features.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)

const authStore = useAuthStore(pinia)
setUnauthorizedHandler(async () => {
  const currentRoute = router.currentRoute.value
  if (currentRoute.path.startsWith('/visitor')) {
    try {
      return await authStore.recoverGuestSession()
    } catch {
      authStore.logout(true)
      await router.replace('/')
      return null
    }
  }
  authStore.logout(true)
  if (currentRoute.path.startsWith('/admin') && currentRoute.name !== 'admin-login') await router.replace('/admin/login')
  return null
})

app.use(router)

app.mount('#app')
