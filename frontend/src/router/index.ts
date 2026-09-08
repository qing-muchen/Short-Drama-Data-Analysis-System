import { createRouter, createWebHistory } from 'vue-router'

import { useUserStore } from '../stores/user'
import LoginView from '../views/Login.vue'
import PlaceholderView from '../views/PlaceholderView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'home', component: PlaceholderView },
    { path: '/login', name: 'login', component: LoginView },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: PlaceholderView,
      meta: { requiresAuth: true },
    },
  ],
})

router.beforeEach(async (to) => {
  const userStore = useUserStore()

  if (to.meta.requiresAuth && !userStore.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (to.meta.requiresAuth && !userStore.currentUser) {
    try {
      await userStore.fetchCurrentUser()
    } catch {
      userStore.logout()
      return { name: 'login', query: { redirect: to.fullPath } }
    }
  }

  if (to.name === 'login' && userStore.isAuthenticated) {
    return { name: 'dashboard' }
  }

  return true
})

export default router
