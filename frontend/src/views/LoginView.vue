<script setup lang="ts">
import { CircleCheck, Lock, User, Warning } from '@element-plus/icons-vue'
import { isAxiosError } from 'axios'
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { checkUsernameAvailability, type UsernameConflictDetail } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

type AuthMode = 'visitor-login' | 'visitor-register' | 'admin-login'

const router = useRouter()
const authStore = useAuthStore()
const mode = ref<AuthMode>('visitor-login')
const loading = ref(false)
const availabilityLoading = ref(false)
const availability = ref<'idle' | 'available' | 'taken'>('idle')
const suggestions = ref<string[]>([])
const visitorLoginForm = reactive({ username: '', password: '' })
const registerForm = reactive({ username: '', password: '', confirmPassword: '' })
const adminForm = reactive({ username: 'admin', password: '' })
const usernamePattern = /^[A-Za-z0-9_]{3,32}$/

function resetAvailability() {
  availability.value = 'idle'
  suggestions.value = []
}

async function checkUsername() {
  const username = registerForm.username.trim()
  if (!usernamePattern.test(username)) {
    resetAvailability()
    return false
  }
  availabilityLoading.value = true
  try {
    const response = await checkUsernameAvailability(username)
    availability.value = response.data.available ? 'available' : 'taken'
    suggestions.value = response.data.suggestions
    return response.data.available
  } catch {
    resetAvailability()
    return false
  } finally {
    availabilityLoading.value = false
  }
}

async function chooseSuggestion(username: string) {
  registerForm.username = username
  resetAvailability()
  await checkUsername()
}

function applyConflict(detail: UsernameConflictDetail) {
  availability.value = 'taken'
  suggestions.value = detail.suggestions
  ElMessage.warning(detail.message)
}

async function submit() {
  if (loading.value) return
  loading.value = true
  try {
    if (mode.value === 'visitor-login') {
      await authStore.loginVisitor({ username: visitorLoginForm.username.trim(), password: visitorLoginForm.password })
      ElMessage.success('登录成功')
      await router.push('/visitor')
      return
    }
    if (mode.value === 'visitor-register') {
      if (!usernamePattern.test(registerForm.username.trim())) {
        ElMessage.warning('账号需为 3-32 位字母、数字或下划线')
        return
      }
      if (registerForm.password.length < 8) {
        ElMessage.warning('密码至少需要 8 位')
        return
      }
      if (registerForm.password !== registerForm.confirmPassword) {
        ElMessage.warning('两次输入的密码不一致')
        return
      }
      if (!(await checkUsername())) return
      await authStore.registerVisitor({ username: registerForm.username.trim(), password: registerForm.password })
      ElMessage.success('注册成功，已为你自动登录')
      await router.push('/visitor')
      return
    }
    await authStore.loginAdmin({ username: adminForm.username.trim(), password: adminForm.password })
    ElMessage.success('管理员登录成功')
    await router.push('/admin')
  } catch (error) {
    if (mode.value === 'visitor-register' && isAxiosError(error) && error.response?.status === 409) {
      const detail = error.response.data?.detail as UsernameConflictDetail | undefined
      if (detail?.code === 'username_taken') {
        applyConflict(detail)
        return
      }
    }
    ElMessage.error(mode.value === 'visitor-register' ? '注册失败，请检查填写内容' : '账号或密码不正确')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-intro" aria-label="品牌介绍">
      <div class="login-brand"><span class="brand-seal" aria-hidden="true">灵</span><span><strong>灵境智游</strong><small>景区导览服务</small></span></div>
      <div class="login-copy">
        <p class="login-kicker">灵山胜境 · 拈花湾</p>
        <h1>一程山水，一路有知</h1>
        <p>登录后查看景点信息并规划游览路线。</p>
      </div>
    </section>

    <section class="login-panel" aria-label="账号入口">
      <div class="login-panel-heading"><span>欢迎使用</span><h2>进入灵境智游</h2><p>请选择登录方式</p></div>
      <el-tabs v-model="mode" class="auth-tabs" stretch>
        <el-tab-pane label="游客登录" name="visitor-login">
          <el-form label-position="top" @submit.prevent="submit">
            <el-form-item label="游客账号" required><el-input v-model="visitorLoginForm.username" :prefix-icon="User" placeholder="请输入账号" size="large" autocomplete="username" /></el-form-item>
            <el-form-item label="登录密码" required><el-input v-model="visitorLoginForm.password" :prefix-icon="Lock" placeholder="请输入密码" show-password size="large" type="password" autocomplete="current-password" /></el-form-item>
            <el-button class="login-submit" type="primary" size="large" :loading="loading" :disabled="!visitorLoginForm.username.trim() || !visitorLoginForm.password" @click="submit">登录游客端</el-button>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="注册账号" name="visitor-register">
          <el-form label-position="top" @submit.prevent="submit">
            <el-form-item label="设置账号" required>
              <el-input v-model="registerForm.username" :prefix-icon="User" placeholder="3-32 位字母、数字或下划线" size="large" autocomplete="username" :loading="availabilityLoading" @input="resetAvailability" @blur="checkUsername" />
            </el-form-item>
            <div v-if="availability === 'available'" class="username-status success"><el-icon><CircleCheck /></el-icon><span>该账号可以使用</span></div>
            <div v-else-if="availability === 'taken'" class="username-conflict" role="alert">
              <div><el-icon><Warning /></el-icon><span>账号名已被占用，请更改</span></div>
              <p>也可以选择以下可用账号：</p>
              <div class="username-suggestions"><button v-for="item in suggestions" :key="item" type="button" @click="chooseSuggestion(item)">{{ item }}</button></div>
            </div>
            <el-form-item label="设置密码" required><el-input v-model="registerForm.password" :prefix-icon="Lock" placeholder="至少 8 位" show-password size="large" type="password" autocomplete="new-password" /></el-form-item>
            <el-form-item label="确认密码" required><el-input v-model="registerForm.confirmPassword" :prefix-icon="Lock" placeholder="再次输入密码" show-password size="large" type="password" autocomplete="new-password" /></el-form-item>
            <p class="form-helper">注册成功后将直接登录，随后选择你的兴趣标签。</p>
            <el-button class="login-submit" type="primary" size="large" :loading="loading" :disabled="!registerForm.username.trim() || !registerForm.password || !registerForm.confirmPassword" @click="submit">注册并进入</el-button>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="管理员" name="admin-login">
          <el-form label-position="top" @submit.prevent="submit">
            <el-form-item label="管理员账号" required><el-input v-model="adminForm.username" :prefix-icon="User" size="large" autocomplete="username" /></el-form-item>
            <el-form-item label="管理员密码" required><el-input v-model="adminForm.password" :prefix-icon="Lock" placeholder="请输入密码" show-password size="large" type="password" autocomplete="current-password" /></el-form-item>
            <el-button class="login-submit" type="primary" size="large" :loading="loading" :disabled="!adminForm.username.trim() || !adminForm.password" @click="submit">进入管理端</el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </section>
  </main>
</template>
