import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { useScenicStore } from '@/stores/scenic'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'landing', component: () => import('@/views/LandingView.vue') },
    { path: '/login', redirect: '/admin/login' },
    { path: '/admin/login', name: 'admin-login', component: () => import('@/views/LoginView.vue') },
    { path: '/visitor', name: 'visitor', component: () => import('@/views/VisitorHomeView.vue'), meta: { requiresAuth: true, role: 'visitor' } },
    { path: '/visitor/guide', name: 'visitor-guide', component: () => import('@/views/VisitorView.vue'), meta: { requiresAuth: true, role: 'visitor' } },
    { path: '/visitor/spots', name: 'visitor-spots', component: () => import('@/views/SpotListView.vue'), meta: { requiresAuth: true, role: 'visitor' } },
    { path: '/visitor/spots/:id', name: 'visitor-spot-detail', component: () => import('@/views/SpotDetailView.vue'), meta: { requiresAuth: true, role: 'visitor' } },
    { path: '/visitor/routes', name: 'visitor-routes', component: () => import('@/views/RouteRecommendView.vue'), meta: { requiresAuth: true, role: 'visitor' } },
    { path: '/visitor/account', redirect: '/visitor' },
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
  const scenicStore = useScenicStore()
  await authStore.initializeSession()
  if (to.name === 'admin-login' && authStore.user?.role === 'admin') return '/admin'
  if (!to.meta.requiresAuth) return true
  if (to.meta.role === 'visitor') {
    if (authStore.user?.role === 'admin') return '/admin'
    const hasScenicContext = Boolean(scenicStore.selectedCode || to.query.scenic_code || to.query.route_id)
    if (!hasScenicContext) return '/'
    try { await authStore.ensureGuestSession() }
    catch { return '/' }
    return true
  }
  if (!authStore.isAuthenticated) return '/admin/login'
  if (to.meta.role && authStore.user?.role !== to.meta.role) return authStore.user?.role === 'admin' ? '/admin' : '/'
  return true
})

export default router
