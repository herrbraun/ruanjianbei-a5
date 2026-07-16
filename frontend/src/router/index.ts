import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/login' },
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue') },
    { path: '/visitor', name: 'visitor', component: () => import('@/views/VisitorHomeView.vue'), meta: { requiresAuth: true, role: 'visitor' } },
    { path: '/visitor/guide', name: 'visitor-guide', component: () => import('@/views/VisitorView.vue'), meta: { requiresAuth: true, role: 'visitor' } },
    { path: '/visitor/spots', name: 'visitor-spots', component: () => import('@/views/SpotListView.vue'), meta: { requiresAuth: true, role: 'visitor' } },
    { path: '/visitor/spots/:id', name: 'visitor-spot-detail', component: () => import('@/views/SpotDetailView.vue'), meta: { requiresAuth: true, role: 'visitor' } },
    { path: '/visitor/routes', name: 'visitor-routes', component: () => import('@/views/RouteRecommendView.vue'), meta: { requiresAuth: true, role: 'visitor' } },
    { path: '/visitor/account', name: 'visitor-account', component: () => import('@/views/UserAccountView.vue'), meta: { requiresAuth: true, role: 'visitor' } },
    { path: '/admin', name: 'admin', component: () => import('@/views/AdminView.vue'), meta: { requiresAuth: true, role: 'admin' } },
    { path: '/admin/spots', name: 'admin-spots', component: () => import('@/views/AdminSpotView.vue'), meta: { requiresAuth: true, role: 'admin' } },
    { path: '/admin/analytics', name: 'admin-analytics', component: () => import('@/views/AdminAnalyticsView.vue'), meta: { requiresAuth: true, role: 'admin' } },
    { path: '/admin/insights', name: 'admin-insights', component: () => import('@/views/AdminInsightsView.vue'), meta: { requiresAuth: true, role: 'admin' } },
    { path: '/admin/media', name: 'admin-media', component: () => import('@/views/AdminMediaView.vue'), meta: { requiresAuth: true, role: 'admin' } },
    { path: '/admin/routes', name: 'admin-routes', component: () => import('@/views/AdminRouteView.vue'), meta: { requiresAuth: true, role: 'admin' } },
    { path: '/admin/knowledge', name: 'admin-knowledge', component: () => import('@/views/KnowledgeView.vue'), meta: { requiresAuth: true, role: 'admin' } },
    { path: '/admin/avatars', name: 'admin-avatars', component: () => import('@/views/AvatarManagementView.vue'), meta: { requiresAuth: true, role: 'admin' } },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore()
  await authStore.initializeSession()
  if (to.name === 'login' && authStore.isAuthenticated) return authStore.user?.role === 'admin' ? '/admin' : '/visitor'
  if (!to.meta.requiresAuth) return true
  if (!authStore.isAuthenticated) return '/login'
  if (to.meta.role && authStore.user?.role !== to.meta.role) return authStore.user?.role === 'admin' ? '/admin' : '/visitor'
  return true
})

export default router
