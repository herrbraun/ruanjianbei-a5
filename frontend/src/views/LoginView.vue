<script setup lang="ts">
import { Lock, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

type LoginMode = 'visitor' | 'admin'

const router = useRouter()
const authStore = useAuthStore()
const mode = ref<LoginMode>('visitor')
const loading = ref(false)

const visitorForm = reactive({
  nickname: '',
  interest: '',
})

const adminForm = reactive({
  username: 'admin',
  password: '',
})

async function submit() {
  loading.value = true
  try {
    if (mode.value === 'visitor') {
      await authStore.loginVisitor({
        nickname: visitorForm.nickname.trim(),
        interest: visitorForm.interest.trim() || undefined,
      })
      ElMessage.success('游客登录成功')
      router.push('/visitor')
      return
    }

    await authStore.loginAdmin({
      username: adminForm.username.trim(),
      password: adminForm.password,
    })
    ElMessage.success('管理员登录成功')
    router.push('/admin')
  } catch {
    ElMessage.error('登录失败，请检查输入信息')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-intro" aria-label="系统介绍">
      <div>
        <span class="brand-mark">AI</span>
        <h1>AI数字人景区导览系统</h1>
        <p>
          第一阶段骨架已预留游客端和管理后台入口。登录后即可进入对应工作区，后续可以并行接入数字人交互、RAG 知识库、语音服务和运营分析。
        </p>

        <div class="status-strip" aria-label="当前骨架能力">
          <span>PostgreSQL 用户体系</span>
          <span>JWT 鉴权</span>
          <span>角色路由守卫</span>
        </div>
      </div>

      <div class="preview-grid">
        <article class="preview-panel">
          <h2>游客端</h2>
          <p>面向游客的数字人导游入口。</p>
          <ul>
            <li>智能问答</li>
            <li>语音输入</li>
            <li>路线推荐</li>
          </ul>
        </article>
        <article class="preview-panel">
          <h2>管理后台</h2>
          <p>面向景区管理方的数据和知识库入口。</p>
          <ul>
            <li>知识库管理</li>
            <li>问答记录</li>
            <li>游客感受度报告</li>
          </ul>
        </article>
      </div>
    </section>

    <section class="login-panel" aria-label="登录表单">
      <h2>进入系统</h2>
      <p>选择身份后登录到对应页面。</p>

      <el-radio-group v-model="mode" class="role-switch">
        <el-radio-button label="visitor">游客登录</el-radio-button>
        <el-radio-button label="admin">管理员登录</el-radio-button>
      </el-radio-group>

      <el-form v-if="mode === 'visitor'" label-position="top" @submit.prevent="submit">
        <el-form-item label="游客昵称" required>
          <el-input v-model="visitorForm.nickname" :prefix-icon="User" placeholder="例如：游客001" size="large" />
        </el-form-item>
        <el-form-item label="兴趣偏好">
          <el-input v-model="visitorForm.interest" placeholder="例如：历史文化、自然风光" size="large" />
        </el-form-item>
        <div class="login-actions">
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            :disabled="!visitorForm.nickname.trim()"
            @click="submit"
          >
            进入系统
          </el-button>
          <span class="hint-text">游客登录会创建一条游客记录，并写入登录日志。</span>
        </div>
      </el-form>

      <el-form v-else label-position="top" @submit.prevent="submit">
        <el-form-item label="管理员账号" required>
          <el-input v-model="adminForm.username" :prefix-icon="User" size="large" />
        </el-form-item>
        <el-form-item label="管理员密码" required>
          <el-input
            v-model="adminForm.password"
            :prefix-icon="Lock"
            placeholder="默认密码：123456"
            show-password
            size="large"
            type="password"
          />
        </el-form-item>
        <div class="login-actions">
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            :disabled="!adminForm.username.trim() || !adminForm.password"
            @click="submit"
          >
            进入系统
          </el-button>
          <span class="hint-text">管理员账号来自数据库，初始账号由后端脚本创建。</span>
        </div>
      </el-form>
    </section>
  </main>
</template>
