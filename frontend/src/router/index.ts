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
      component: () => import('../views/Dashboard.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/dramas',
      name: 'dramas',
      component: () => import('../views/drama/DramaList.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/actors',
      name: 'actors',
      component: () => import('../views/master/ActorList.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/platforms',
      name: 'platforms',
      component: () => import('../views/master/PlatformList.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/imports',
      name: 'imports',
      component: () => import('../views/import/ImportUpload.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/imports/:id',
      name: 'import-job',
      component: () => import('../views/import/ImportJobs.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/imports/:id/errors',
      name: 'import-errors',
      component: () => import('../views/import/ImportErrors.vue'),
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
