import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import AdminView from '@/views/AdminView.vue'
import AvatarManagementView from '@/views/AvatarManagementView.vue'
import KnowledgeView from '@/views/KnowledgeView.vue'
import LoginView from '@/views/LoginView.vue'
import VisitorView from '@/views/VisitorView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/login' },
    { path: '/login', name: 'login', component: LoginView },
    {
      path: '/visitor',
      name: 'visitor',
      component: VisitorView,
      meta: { requiresAuth: true, role: 'visitor' },
    },
    {
      path: '/admin',
      name: 'admin',
      component: AdminView,
      meta: { requiresAuth: true, role: 'admin' },
    },
    {
      path: '/admin/knowledge',
      name: 'admin-knowledge',
      component: KnowledgeView,
      meta: { requiresAuth: true, role: 'admin' },
    },
    {
      path: '/admin/avatars',
      name: 'admin-avatars',
      component: AvatarManagementView,
      meta: { requiresAuth: true, role: 'admin' },
    },
  ],
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore()
  await authStore.initializeSession()

  if (to.name === 'login' && authStore.isAuthenticated) {
    return authStore.user?.role === 'admin' ? '/admin' : '/visitor'
  }

  if (!to.meta.requiresAuth) {
    return true
  }

  if (!authStore.isAuthenticated) {
    return '/login'
  }

  if (to.meta.role && authStore.user?.role !== to.meta.role) {
    return authStore.user?.role === 'admin' ? '/admin' : '/visitor'
  }

  return true
})

export default router
