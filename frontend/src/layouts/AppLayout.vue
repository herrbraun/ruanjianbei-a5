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
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { getInterestOptions, resolveAssetUrl, updateProfile } from '@/api/auth'
import InterestSelector from '@/components/InterestSelector.vue'
import { useAuthStore } from '@/stores/auth'

defineProps<{
  title: string
  description: string
  roleLabel: string
}>()

interface NavigationItem {
  label: string
  to?: string
  icon: Component
}

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const drawerVisible = ref(false)
const interestDialogVisible = ref(false)
const interestLoading = ref(false)
const interestSaving = ref(false)
const interestLoadError = ref(false)
const interestOptions = ref<string[]>([])
const selectedInterests = ref<string[]>([])

const displayName = computed(() => authStore.user?.nickname || authStore.user?.username || '未命名用户')
const roleName = computed(() => (authStore.user?.role === 'admin' ? '景区管理员' : '游客'))
const avatarUrl = computed(() => resolveAssetUrl(authStore.user?.avatar_url))
const navigation = computed<NavigationItem[]>(() => {
  if (authStore.user?.role === 'admin') {
    return [
      { label: '管理首页', to: '/admin', icon: House },
      { label: '景点管理', to: '/admin/spots', icon: Location },
      { label: '素材管理', to: '/admin/media', icon: Picture },
      { label: '路线与反馈', to: '/admin/routes', icon: Tickets },
      { label: '知识库', to: '/admin/knowledge', icon: Collection },
      { label: '数字人管理', to: '/admin/avatars', icon: UserFilled },
      { label: '运营统计', to: '/admin/analytics', icon: DataAnalysis },
    ]
  }
  return [
    { label: '游客首页', to: '/visitor', icon: House },
    { label: '景点浏览', to: '/visitor/spots', icon: Location },
    { label: '路线推荐', to: '/visitor/routes', icon: MapLocation },
    { label: '智能导览', to: '/visitor/guide', icon: ChatDotRound },
    { label: '账号管理', to: '/visitor/account', icon: User },
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
  authStore.logout()
  router.push('/login')
}

async function loadInterestOptions() {
  interestLoading.value = true
  interestLoadError.value = false
  try {
    interestOptions.value = (await getInterestOptions()).data.interests
  } catch {
    interestLoadError.value = true
  } finally {
    interestLoading.value = false
  }
}

async function saveInitialInterests() {
  if (!selectedInterests.value.length) {
    ElMessage.warning('请至少选择一个兴趣标签')
    return
  }
  interestSaving.value = true
  try {
    const response = await updateProfile({ interests: selectedInterests.value })
    authStore.setUser(response.data)
    interestDialogVisible.value = false
    ElMessage.success('兴趣偏好已保存')
  } catch {
    ElMessage.error('兴趣偏好保存失败，请重试')
  } finally {
    interestSaving.value = false
  }
}

onMounted(async () => {
  if (authStore.user?.role !== 'visitor' || !authStore.user.needs_interest_setup) return
  selectedInterests.value = [...authStore.user.interests]
  interestDialogVisible.value = true
  await loadInterestOptions()
})
</script>

<template>
  <div class="app-shell">
    <a class="skip-link" href="#main-content">跳到主要内容</a>

    <aside class="app-sidebar" aria-label="主导航">
      <RouterLink class="brand-lockup" :to="authStore.user?.role === 'admin' ? '/admin' : '/visitor'">
        <span class="brand-seal" aria-hidden="true">灵</span>
        <span><strong>灵境智游</strong><small>景区导览服务</small></span>
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

      <div class="sidebar-account">
        <div class="account-avatar" aria-hidden="true"><img v-if="avatarUrl" :src="avatarUrl" alt=""><el-icon v-else><User /></el-icon></div>
        <div><strong>{{ displayName }}</strong><span>{{ roleName }}</span></div>
        <el-button :icon="SwitchButton" text circle aria-label="退出登录" title="退出登录" @click="logout" />
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

      <main id="main-content" class="page-container" tabindex="-1">
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
        <div class="brand-lockup"><span class="brand-seal" aria-hidden="true">灵</span><span><strong>灵境智游</strong><small>景区导览服务</small></span></div>
        <nav class="sidebar-nav" aria-label="移动端主导航">
          <button v-for="item in navigation" :key="item.label" class="nav-item" :class="{ active: isActive(item) }" type="button" @click="navigate(item)">
            <el-icon><component :is="item.icon" /></el-icon><span>{{ item.label }}</span>
          </button>
        </nav>
        <div class="sidebar-account"><div class="account-avatar" aria-hidden="true"><img v-if="avatarUrl" :src="avatarUrl" alt=""><el-icon v-else><User /></el-icon></div><div><strong>{{ displayName }}</strong><span>{{ roleName }}</span></div><el-button :icon="SwitchButton" text circle aria-label="退出登录" @click="logout" /></div>
      </div>
    </el-drawer>

    <el-dialog v-model="interestDialogVisible" class="interest-onboarding-dialog" width="min(92vw, 620px)" :show-close="false" :close-on-click-modal="false" :close-on-press-escape="false" :append-to-body="true">
      <template #header><div class="dialog-heading"><span>完善首次设置</span><h2>选择你感兴趣的内容</h2><p>这些标签会用于景点筛选和路线推荐，之后可在账号管理中修改。</p></div></template>
      <div v-loading="interestLoading">
        <el-alert v-if="interestLoadError" title="兴趣标签加载失败" type="error" :closable="false" show-icon><template #default><el-button text type="primary" @click="loadInterestOptions">重新加载</el-button></template></el-alert>
        <InterestSelector v-else v-model="selectedInterests" :options="interestOptions" :disabled="interestSaving" />
        <p class="selection-count">已选择 {{ selectedInterests.length }} / 8</p>
      </div>
      <template #footer><el-button type="primary" :loading="interestSaving" :disabled="interestLoadError || !selectedInterests.length" @click="saveInitialInterests">保存并开始游览</el-button></template>
    </el-dialog>
  </div>
</template>
