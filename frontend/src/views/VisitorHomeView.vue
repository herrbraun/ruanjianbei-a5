<script setup lang="ts">
import { ArrowRight, ChatDotRound, Location, MapLocation } from '@element-plus/icons-vue'

import AppLayout from '@/layouts/AppLayout.vue'
import { useScenicStore } from '@/stores/scenic'

const scenicStore = useScenicStore()

const services = [
  { title: '发现景点', description: '看看附近有哪些值得游览的景点和服务设施。', to: '/visitor/spots', icon: Location, action: '去看看' },
  { title: '规划路线', description: '按照你的兴趣和时间，安排一条合适的游览路线。', to: '/visitor/routes', icon: MapLocation, action: '规划行程' },
  { title: '随身讲解', description: '听景点故事，也可以询问演出、路线和游览事项。', to: '/visitor/guide', icon: ChatDotRound, action: '开始讲解' },
]
</script>

<template>
  <AppLayout title="开始游览" description="找景点、定路线，边走边听讲解。" role-label="景区导览">
    <template #actions><RouterLink to="/visitor/routes"><el-button type="primary" :icon="MapLocation">规划路线</el-button></RouterLink></template>
    <section class="welcome-band">
      <div><p>{{ scenicStore.selectedName || '本次游览' }}</p><h2>准备从哪里开始？</h2><span>你可以先看看景点，也可以直接规划一条路线。</span></div>
      <RouterLink class="welcome-action" to="/visitor/spots"><span>浏览全部景点</span><el-icon><ArrowRight /></el-icon></RouterLink>
    </section>
    <section class="section-block">
      <div class="section-heading"><div><span>游览助手</span><h2>接下来做什么？</h2></div></div>
      <div class="action-grid">
        <RouterLink v-for="service in services" :key="service.to" class="action-tile" :to="service.to">
          <el-icon><component :is="service.icon" /></el-icon>
          <div><h3>{{ service.title }}</h3><p>{{ service.description }}</p><span>{{ service.action }} <el-icon><ArrowRight /></el-icon></span></div>
        </RouterLink>
      </div>
    </section>
  </AppLayout>
</template>
