<script setup lang="ts">
import { ArrowRight, Collection, DataAnalysis, Location, Picture, Tickets, UserFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

import { getAnalyticsOverview, type AnalyticsOverview } from '@/api/analytics'
import AppLayout from '@/layouts/AppLayout.vue'

const loading = ref(false)
const overview = ref<AnalyticsOverview | null>(null)

const metrics = computed(() => [
  { label: '已上架景点', value: overview.value?.enabled_spot_count ?? '--', note: `共 ${overview.value?.spot_count ?? '--'} 个景点` },
  { label: '游客行程', value: overview.value?.route_count ?? '--', note: '累计生成路线' },
  { label: '路线评价', value: overview.value?.feedback_count ?? '--', note: overview.value?.average_rating ? `平均 ${overview.value.average_rating} 分` : '暂无评分' },
])

const entries = computed(() => [
  { title: '景点管理', description: '维护景点介绍、开放时间和展示状态。', to: '/admin/spots', icon: Location, meta: `${overview.value?.spot_count ?? '--'} 个景点` },
  { title: '素材管理', description: '管理景点图片、视频和音频。', to: '/admin/media', icon: Picture, meta: `${overview.value?.media_count ?? '--'} 个素材` },
  { title: '路线与反馈', description: '调整推荐设置，查看游客行程与评价。', to: '/admin/routes', icon: Tickets, meta: `${overview.value?.route_count ?? '--'} 条行程` },
  { title: '知识库', description: '维护景区资料和智能问答检索配置。', to: '/admin/knowledge', icon: Collection, meta: '管理资料' },
  { title: '数字人管理', description: '维护讲解员形象及景区启用配置。', to: '/admin/avatars', icon: UserFilled, meta: '管理形象' },
  { title: '运营统计', description: '查看路线使用、景点热度和游客反馈。', to: '/admin/analytics', icon: DataAnalysis, meta: '查看统计' },
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
  <AppLayout title="管理工作台" description="管理景点内容、路线设置和游客反馈。" role-label="运营管理">
    <template #actions><RouterLink to="/admin/spots"><el-button type="primary" :icon="Location">管理景点</el-button></RouterLink></template>
    <section v-loading="loading" class="admin-overview-band"><div v-for="metric in metrics" :key="metric.label"><span>{{ metric.label }}</span><strong>{{ metric.value }}</strong><p>{{ metric.note }}</p></div></section>
    <section class="section-block">
      <div class="section-heading"><div><span>快捷入口</span><h2>日常管理</h2></div></div>
      <div class="admin-entry-list">
        <RouterLink v-for="entry in entries" :key="entry.to" class="admin-entry" :to="entry.to">
          <el-icon><component :is="entry.icon" /></el-icon><div><h3>{{ entry.title }}</h3><p>{{ entry.description }}</p></div><span>{{ entry.meta }}</span><el-icon><ArrowRight /></el-icon>
        </RouterLink>
      </div>
    </section>
  </AppLayout>
</template>
