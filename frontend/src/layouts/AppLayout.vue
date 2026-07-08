<script setup lang="ts">
import { SwitchButton } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const props = defineProps<{
  title: string
  description: string
  roleLabel: string
}>()

const router = useRouter()
const authStore = useAuthStore()

const displayName = computed(() => {
  return authStore.user?.nickname || authStore.user?.username || '未命名用户'
})

function logout() {
  authStore.logout()
  router.push('/login')
}
</script>

<template>
  <main class="workspace-shell">
    <header class="workspace-header">
      <div>
        <p class="system-name">AI数字人景区导览系统</p>
        <h1>{{ props.title }}</h1>
        <p>{{ props.description }}</p>
      </div>

      <div class="identity-panel">
        <div>
          <span>{{ props.roleLabel }}</span>
          <strong>{{ displayName }}</strong>
        </div>
        <el-button :icon="SwitchButton" plain @click="logout">退出</el-button>
      </div>
    </header>

    <slot />
  </main>
</template>
