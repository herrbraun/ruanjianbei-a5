<script setup lang="ts">
import { ArrowRight, ChatDotRound, Location, MapLocation, User } from '@element-plus/icons-vue'

import AppLayout from '@/layouts/AppLayout.vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

const services = [
  { title: '景点浏览', description: '按所属景区、类型和兴趣标签查找景点。', to: '/visitor/spots', icon: Location, action: '查看景点' },
  { title: '路线推荐', description: '结合兴趣、游玩时长和起点生成路线。', to: '/visitor/routes', icon: MapLocation, action: '开始规划' },
  { title: '智能导览', description: '通过文字或语音获取景区讲解与游览建议。', to: '/visitor/guide', icon: ChatDotRound, action: '开始导览' },
  { title: '个人中心', description: '管理头像、昵称、兴趣偏好和登录密码。', to: '/visitor/account', icon: User, action: '查看账号' },
]
</script>

<template>
  <AppLayout title="今日游览" description="查看景点信息，规划适合你的游览路线。" role-label="游览服务">
    <template #actions><RouterLink to="/visitor/routes"><el-button type="primary" :icon="MapLocation">规划路线</el-button></RouterLink></template>
    <section class="welcome-band">
      <div><p>欢迎，{{ authStore.user?.nickname }}</p><h2>准备从哪里开始？</h2><span>当前兴趣：{{ authStore.user?.interest || '尚未设置' }}</span></div>
      <RouterLink class="welcome-action" to="/visitor/spots"><span>浏览全部景点</span><el-icon><ArrowRight /></el-icon></RouterLink>
    </section>
    <section class="section-block">
      <div class="section-heading"><div><span>游览服务</span><h2>选择下一步</h2></div></div>
      <div class="action-grid">
        <RouterLink v-for="service in services" :key="service.to" class="action-tile" :to="service.to">
          <el-icon><component :is="service.icon" /></el-icon>
          <div><h3>{{ service.title }}</h3><p>{{ service.description }}</p><span>{{ service.action }} <el-icon><ArrowRight /></el-icon></span></div>
        </RouterLink>
      </div>
    </section>
  </AppLayout>
</template>
