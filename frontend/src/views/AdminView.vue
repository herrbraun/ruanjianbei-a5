<script setup lang="ts">
import { ArrowRight, Collection, DataAnalysis, Location, Picture, Tickets, UserFilled } from '@element-plus/icons-vue'
import { computed, onMounted, ref } from 'vue'

import { getAnalyticsOverview, type AnalyticsOverview } from '@/api/analytics'
import AppLayout from '@/layouts/AppLayout.vue'

const loading = ref(false)
const overview = ref<AnalyticsOverview | null>(null)

const metrics = computed(() => [
  { label: '已上架景点', value: overview.value?.enabled_spot_count ?? '--', note: `共 ${overview.value?.spot_count ?? '--'} 个景点` },
  { label: '已规划行程', value: overview.value?.route_count ?? '--', note: '累计生成路线' },
  { label: '收到评价', value: overview.value?.feedback_count ?? '--', note: overview.value?.average_rating ? `平均 ${overview.value.average_rating} 分` : '暂无评分' },
])

const entries = computed(() => [
  { title: '景点内容', description: '维护景点介绍、开放安排和游客端展示状态。', to: '/admin/spots', icon: Location, meta: `${overview.value?.spot_count ?? '--'} 个景点` },
  { title: '景点素材', description: '管理景点图片、视频和语音介绍。', to: '/admin/media', icon: Picture, meta: `${overview.value?.media_count ?? '--'} 项内容` },
  { title: '路线评价', description: '调整路线安排方式，查看游客行程与评价。', to: '/admin/routes', icon: Tickets, meta: `${overview.value?.route_count ?? '--'} 条行程` },
  { title: '问答资料', description: '维护讲解员回答游客问题时参考的景区资料。', to: '/admin/knowledge', icon: Collection, meta: '维护资料' },
  { title: '讲解员', description: '维护讲解员形象、声音和服务景区。', to: '/admin/avatars', icon: UserFilled, meta: '管理讲解员' },
  { title: '运营概览', description: '查看路线使用、景点热度和游客感受。', to: '/admin/analytics', icon: DataAnalysis, meta: '查看概览' },
])

async function loadOverview() {
  loading.value = true
  try { overview.value = (await getAnalyticsOverview()).data }
  catch { ElMessage.error('工作台加载失败，请稍后重试') }
  finally { loading.value = false }
}

onMounted(loadOverview)
</script>

<template>
  <AppLayout title="运营首页" description="查看今日重点，快速进入各项运营工作。" role-label="景区运营">
    <template #actions><RouterLink to="/admin/spots"><el-button type="primary" :icon="Location">管理景点</el-button></RouterLink></template>
    <section v-loading="loading" class="admin-overview-band"><div v-for="metric in metrics" :key="metric.label"><span>{{ metric.label }}</span><strong>{{ metric.value }}</strong><p>{{ metric.note }}</p></div></section>
    <section class="section-block">
      <div class="section-heading"><div><span>常用功能</span><h2>今天要处理什么？</h2></div></div>
      <div class="admin-entry-list">
        <RouterLink v-for="entry in entries" :key="entry.to" class="admin-entry" :to="entry.to">
          <el-icon><component :is="entry.icon" /></el-icon><div><h3>{{ entry.title }}</h3><p>{{ entry.description }}</p></div><span>{{ entry.meta }}</span><el-icon><ArrowRight /></el-icon>
        </RouterLink>
      </div>
    </section>
  </AppLayout>
</template>
