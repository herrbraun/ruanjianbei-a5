<script setup lang="ts">
import {
  DataAnalysis,
  ChatDotRound,
  Collection,
  House,
  Lock,
  Location,
  MapLocation,
  Menu,
  Picture,
  SwitchButton,
  Tickets,
  User,
  UserFilled,
} from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { computed, nextTick, reactive, ref, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { changeAdminPassword, resolveAssetUrl } from '@/api/auth'
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
const passwordDialogVisible = ref(false)
const passwordSubmitting = ref(false)
const passwordFormRef = ref<FormInstance>()
const passwordForm = reactive({ currentPassword: '', newPassword: '', confirmPassword: '' })

function validateNewPassword(_rule: unknown, value: string, callback: (error?: Error) => void) {
  if (!value) return callback(new Error('请输入新密码'))
  if (value.length < 12 || value.length > 64) return callback(new Error('新密码须为 12–64 个字符'))
  if (new TextEncoder().encode(value).length > 72) return callback(new Error('新密码 UTF-8 编码不能超过 72 字节'))
  if (value === passwordForm.currentPassword) return callback(new Error('新密码不能与当前密码相同'))
  callback()
}

function validatePasswordConfirmation(_rule: unknown, value: string, callback: (error?: Error) => void) {
  if (!value) return callback(new Error('请再次输入新密码'))
  if (value !== passwordForm.newPassword) return callback(new Error('两次输入的新密码不一致'))
  callback()
}

const passwordRules: FormRules = {
  currentPassword: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  newPassword: [{ validator: validateNewPassword, trigger: ['blur', 'change'] }],
  confirmPassword: [{ validator: validatePasswordConfirmation, trigger: ['blur', 'change'] }],
}

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

function openPasswordDialog() {
  if (authStore.user?.role !== 'admin') return
  drawerVisible.value = false
  passwordDialogVisible.value = true
}

function resetPasswordForm() {
  passwordForm.currentPassword = ''
  passwordForm.newPassword = ''
  passwordForm.confirmPassword = ''
  void nextTick(() => passwordFormRef.value?.clearValidate())
}

function passwordErrorText(error: unknown) {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : '密码修改失败，请稍后重试'
}

async function submitPasswordChange() {
  if (authStore.user?.role !== 'admin' || passwordSubmitting.value) return
  const valid = await passwordFormRef.value?.validate().catch(() => false)
  if (!valid) return
  passwordSubmitting.value = true
  try {
    await changeAdminPassword({
      current_password: passwordForm.currentPassword,
      new_password: passwordForm.newPassword,
    })
    passwordDialogVisible.value = false
    ElMessage.success('密码修改成功，请重新登录')
    authStore.logout(true)
    await router.replace('/admin/login')
  } catch (error) {
    ElMessage.error(passwordErrorText(error))
  } finally {
    passwordSubmitting.value = false
  }
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
        <div class="account-actions">
          <el-button :icon="Lock" text circle aria-label="修改密码" title="修改密码" @click="openPasswordDialog" />
          <el-button :icon="SwitchButton" text circle aria-label="退出登录" title="退出登录" @click="logout" />
        </div>
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
        <div v-if="authStore.user?.role === 'admin'" class="sidebar-account"><div class="account-avatar" aria-hidden="true"><img v-if="avatarUrl" :src="avatarUrl" alt=""><el-icon v-else><User /></el-icon></div><div><strong>{{ displayName }}</strong><span>{{ roleName }}</span></div><div class="account-actions"><el-button :icon="Lock" text circle aria-label="修改密码" title="修改密码" @click="openPasswordDialog" /><el-button :icon="SwitchButton" text circle aria-label="退出登录" title="退出登录" @click="logout" /></div></div>
        <div v-else class="sidebar-account visitor-scenic-account"><div class="account-avatar" aria-hidden="true"><el-icon><Location /></el-icon></div><div><strong>{{ scenicStore.selectedName || '选择景区' }}</strong><span>正在游览</span></div><el-button :icon="SwitchButton" text circle aria-label="切换景区" @click="switchScenicArea" /></div>
      </div>
    </el-drawer>

    <el-dialog
      v-model="passwordDialogVisible"
      class="admin-password-dialog"
      title="修改管理员密码"
      width="min(92vw, 460px)"
      :close-on-click-modal="!passwordSubmitting"
      :close-on-press-escape="!passwordSubmitting"
      :show-close="!passwordSubmitting"
      @closed="resetPasswordForm"
    >
      <p class="password-dialog-note">修改后当前账号将退出，请使用新密码重新登录。</p>
      <el-form ref="passwordFormRef" :model="passwordForm" :rules="passwordRules" label-position="top" @submit.prevent="submitPasswordChange">
        <el-form-item label="当前密码" prop="currentPassword">
          <el-input v-model="passwordForm.currentPassword" type="password" show-password autocomplete="current-password" placeholder="请输入当前密码" />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input v-model="passwordForm.newPassword" type="password" show-password autocomplete="new-password" placeholder="至少 12 个字符" />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirmPassword">
          <el-input v-model="passwordForm.confirmPassword" type="password" show-password autocomplete="new-password" placeholder="再次输入新密码" @keyup.enter="submitPasswordChange" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="passwordSubmitting" @click="passwordDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="passwordSubmitting" @click="submitPasswordChange">确认修改</el-button>
      </template>
    </el-dialog>
  </div>
</template>
