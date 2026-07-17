<script setup lang="ts">
import { ArrowLeft, Lock, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const form = reactive({ username: 'admin', password: '' })

async function submit() {
  if (loading.value || !form.username.trim() || !form.password) return
  loading.value = true
  try {
    await authStore.loginAdmin({ username: form.username.trim(), password: form.password })
    ElMessage.success('管理员登录成功')
    await router.push('/admin')
  } catch {
    ElMessage.error('管理员账号或密码不正确')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-page admin-login-page">
    <section class="login-intro" aria-label="管理端介绍">
      <div class="login-brand"><span class="brand-seal" aria-hidden="true">灵</span><span><strong>灵境智游</strong><small>景区导览服务</small></span></div>
      <div class="login-copy"><p class="login-kicker">SCENIC OPERATIONS</p><h1>景区运营<br>管理中心</h1><p>管理知识库、数字人、景点内容与游客体验数据。</p></div>
    </section>
    <section class="login-panel" aria-label="管理员登录">
      <RouterLink class="admin-login-back" to="/"><el-icon><ArrowLeft /></el-icon> 返回游客首页</RouterLink>
      <div class="login-panel-heading"><span>ADMIN ACCESS</span><h2>管理员登录</h2><p>该入口仅供景区运营人员使用</p></div>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="管理员账号" required><el-input v-model="form.username" :prefix-icon="User" size="large" autocomplete="username" /></el-form-item>
        <el-form-item label="管理员密码" required><el-input v-model="form.password" :prefix-icon="Lock" placeholder="请输入密码" show-password size="large" type="password" autocomplete="current-password" @keyup.enter="submit" /></el-form-item>
        <el-button class="login-submit" type="primary" size="large" :loading="loading" :disabled="!form.username.trim() || !form.password" @click="submit">进入管理后台</el-button>
      </el-form>
    </section>
  </main>
</template>

<style scoped>
.admin-login-back{display:inline-flex;align-items:center;gap:6px;margin-bottom:34px;color:#6a7d79;text-decoration:none;font-size:13px}.admin-login-back:hover{color:#087f72}
</style>
