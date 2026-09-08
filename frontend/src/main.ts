import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

import App from './App.vue'
import { setUnauthorizedHandler } from './api/axios'
import router from './router'
import pinia from './stores'
import { useUserStore } from './stores/user'

const app = createApp(App)
app.use(pinia)

const userStore = useUserStore(pinia)
setUnauthorizedHandler(() => {
  userStore.logout()
  if (router.currentRoute.value.name !== 'login') {
    void router.replace({ name: 'login' })
  }
})

app.use(router).use(ElementPlus).mount('#app')
