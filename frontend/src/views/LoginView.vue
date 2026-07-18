<script setup lang="ts">
import { ArrowLeft, Lock, User } from '@element-plus/icons-vue'
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
      <div class="login-copy"><p class="login-kicker">景区运营</p><h1>景区运营<br>管理中心</h1><p>维护景点与讲解内容，查看路线使用和游客反馈。</p></div>
    </section>
    <section class="login-panel" aria-label="管理员登录">
      <RouterLink class="admin-login-back" to="/"><el-icon><ArrowLeft /></el-icon> 返回游客首页</RouterLink>
      <div class="login-panel-heading"><span>运营人员入口</span><h2>登录管理中心</h2><p>请输入景区运营账号和密码</p></div>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="账号" required><el-input v-model="form.username" :prefix-icon="User" size="large" autocomplete="username" /></el-form-item>
        <el-form-item label="密码" required><el-input v-model="form.password" :prefix-icon="Lock" placeholder="请输入密码" show-password size="large" type="password" autocomplete="current-password" @keyup.enter="submit" /></el-form-item>
        <el-button class="login-submit" type="primary" size="large" :loading="loading" :disabled="!form.username.trim() || !form.password" @click="submit">登录</el-button>
      </el-form>
    </section>
  </main>
</template>

<style scoped>
.admin-login-back{display:inline-flex;align-items:center;gap:6px;margin-bottom:34px;color:#6a7d79;text-decoration:none;font-size:13px}.admin-login-back:hover{color:#087f72}
</style>
