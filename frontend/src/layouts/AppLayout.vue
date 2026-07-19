<script setup lang="ts">
import {
  DataAnalysis,
  ChatDotRound,
  Collection,
  House,
  Location,
  MapLocation,
  Menu,
  Picture,
  SwitchButton,
  Tickets,
  User,
  UserFilled,
} from '@element-plus/icons-vue'
import { computed, ref, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { resolveAssetUrl } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { useScenicStore } from '@/stores/scenic'

withDefaults(defineProps<{
  title: string
  description: string
  roleLabel: string
  immersive?: boolean
}>(), {
  immersive: false,
})

interface NavigationItem {
  label: string
  to?: string
  icon: Component
}

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const scenicStore = useScenicStore()
const drawerVisible = ref(false)

const displayName = computed(() => authStore.user?.nickname || authStore.user?.username || '未命名用户')
const roleName = computed(() => (authStore.user?.role === 'admin' ? '景区运营' : '游客'))
const avatarUrl = computed(() => resolveAssetUrl(authStore.user?.avatar_url))
const navigation = computed<NavigationItem[]>(() => {
  if (authStore.user?.role === 'admin') {
    return [
      { label: '运营首页', to: '/admin', icon: House },
      { label: '景点内容', to: '/admin/spots', icon: Location },
      { label: '景点素材', to: '/admin/media', icon: Picture },
      { label: '路线评价', to: '/admin/routes', icon: Tickets },
      { label: '问答资料', to: '/admin/knowledge', icon: Collection },
      { label: '讲解员', to: '/admin/avatars', icon: UserFilled },
      { label: '运营概览', to: '/admin/analytics', icon: DataAnalysis },
      { label: '服务反馈', to: '/admin/insights', icon: ChatDotRound },
    ]
  }
  return [
    { label: '首页', to: '/visitor', icon: House },
    { label: '找景点', to: '/visitor/spots', icon: Location },
    { label: '规划路线', to: '/visitor/routes', icon: MapLocation },
    { label: '随身讲解', to: '/visitor/guide', icon: ChatDotRound },
  ]
})

function isActive(item: NavigationItem) {
  if (!item.to) return false
  if (item.to === '/visitor' || item.to === '/admin') return route.path === item.to
  return route.path.startsWith(item.to)
}

function navigate(item: NavigationItem) {
  if (!item.to) return
  drawerVisible.value = false
  router.push(item.to)
}

function logout() {
  drawerVisible.value = false
  authStore.logout(true)
  router.push('/')
}

function switchScenicArea() {
  drawerVisible.value = false
  router.push('/')
}
</script>

<template>
  <div class="app-shell">
    <a class="skip-link" href="#main-content">跳到主要内容</a>

    <aside class="app-sidebar" aria-label="主导航">
      <RouterLink class="brand-lockup" :to="authStore.user?.role === 'admin' ? '/admin' : '/visitor'">
        <span class="brand-seal" aria-hidden="true">灵</span>
        <span><strong>灵境智游</strong><small>景点 · 路线 · 讲解</small></span>
      </RouterLink>

      <nav class="sidebar-nav">
        <button
          v-for="item in navigation"
          :key="item.label"
          class="nav-item"
          :class="{ active: isActive(item) }"
          type="button"
          @click="navigate(item)"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <div v-if="authStore.user?.role === 'admin'" class="sidebar-account">
        <div class="account-avatar" aria-hidden="true"><img v-if="avatarUrl" :src="avatarUrl" alt=""><el-icon v-else><User /></el-icon></div>
        <div><strong>{{ displayName }}</strong><span>{{ roleName }}</span></div>
        <el-button :icon="SwitchButton" text circle aria-label="退出登录" title="退出登录" @click="logout" />
      </div>
      <div v-else class="sidebar-account visitor-scenic-account">
        <div class="account-avatar" aria-hidden="true"><el-icon><Location /></el-icon></div>
        <div><strong>{{ scenicStore.selectedName || '选择景区' }}</strong><span>正在游览</span></div>
        <el-button :icon="SwitchButton" text circle aria-label="切换景区" title="切换景区" @click="switchScenicArea" />
      </div>
    </aside>

    <section class="app-main">
      <header class="mobile-appbar">
        <el-button :icon="Menu" text circle aria-label="打开导航" @click="drawerVisible = true" />
        <RouterLink class="mobile-brand" :to="authStore.user?.role === 'admin' ? '/admin' : '/visitor'">
          <span class="brand-seal" aria-hidden="true">灵</span><strong>灵境智游</strong>
        </RouterLink>
        <span class="mobile-role">{{ roleName }}</span>
      </header>

      <main id="main-content" class="page-container" :class="{ 'is-immersive': immersive }" tabindex="-1">
        <header class="page-header">
          <div>
            <p class="page-eyebrow">{{ roleLabel }}</p>
            <h1>{{ title }}</h1>
            <p class="page-description">{{ description }}</p>
          </div>
          <div v-if="$slots.actions" class="page-actions"><slot name="actions" /></div>
        </header>
        <slot />
      </main>
    </section>

    <el-drawer v-model="drawerVisible" direction="ltr" size="min(84vw, 320px)" :with-header="false">
      <div class="mobile-drawer">
        <div class="brand-lockup"><span class="brand-seal" aria-hidden="true">灵</span><span><strong>灵境智游</strong><small>景点 · 路线 · 讲解</small></span></div>
        <nav class="sidebar-nav" aria-label="移动端主导航">
          <button v-for="item in navigation" :key="item.label" class="nav-item" :class="{ active: isActive(item) }" type="button" @click="navigate(item)">
            <el-icon><component :is="item.icon" /></el-icon><span>{{ item.label }}</span>
          </button>
        </nav>
        <div v-if="authStore.user?.role === 'admin'" class="sidebar-account"><div class="account-avatar" aria-hidden="true"><img v-if="avatarUrl" :src="avatarUrl" alt=""><el-icon v-else><User /></el-icon></div><div><strong>{{ displayName }}</strong><span>{{ roleName }}</span></div><el-button :icon="SwitchButton" text circle aria-label="退出登录" @click="logout" /></div>
        <div v-else class="sidebar-account visitor-scenic-account"><div class="account-avatar" aria-hidden="true"><el-icon><Location /></el-icon></div><div><strong>{{ scenicStore.selectedName || '选择景区' }}</strong><span>正在游览</span></div><el-button :icon="SwitchButton" text circle aria-label="切换景区" @click="switchScenicArea" /></div>
      </div>
    </el-drawer>
  </div>
</template>
