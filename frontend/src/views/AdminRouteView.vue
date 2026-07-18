<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import {
  getAdminRoutes,
  getRouteSettings,
  updateRouteSettings,
  type AdminRoute,
  type RouteSettings,
} from '@/api/routes'
import AppLayout from '@/layouts/AppLayout.vue'

const loading = ref(false)
const saving = ref(false)
const routes = ref<AdminRoute[]>([])
const filters = reactive({ interest: '', rating: undefined as number | undefined })
const settings = reactive<RouteSettings>({
  tag_match_weight: 100,
  priority_weight: 1,
  max_spots: 12,
  include_service_points: false,
})

function preferenceLabel(preference: string) {
  return { balanced: '轻松均衡', priority: '必看景点', more_spots: '多逛几处' }[preference] || preference
}

async function loadData() {
  loading.value = true
  try {
    const [routeResponse, settingsResponse] = await Promise.all([
      getAdminRoutes({ interest: filters.interest.trim() || undefined, rating: filters.rating }),
      getRouteSettings(),
    ])
    routes.value = routeResponse.data
    Object.assign(settings, settingsResponse.data)
  } catch {
    ElMessage.error('路线管理数据加载失败')
  } finally {
    loading.value = false
  }
}

async function saveSettings() {
  saving.value = true
  try {
    const response = await updateRouteSettings(settings)
    Object.assign(settings, response.data)
    ElMessage.success('推荐设置已保存')
  } catch {
    ElMessage.error('推荐设置保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(loadData)
</script>

<template>
  <AppLayout title="路线评价" description="调整路线安排方式，查看游客行程与评价。" role-label="景区运营">
    <section class="settings-panel">
      <div class="data-section-header"><div><span>推荐方式</span><h2>路线安排规则</h2><p>修改后将应用于新生成的路线。</p></div><el-tag type="success" effect="plain">使用中</el-tag></div>
      <div class="form-grid">
        <el-form-item label="兴趣契合程度"><el-input-number v-model="settings.tag_match_weight" :min="0" :max="1000" /></el-form-item>
        <el-form-item label="重点景点优先程度"><el-input-number v-model="settings.priority_weight" :min="0" :max="100" :step="0.1" /></el-form-item>
        <el-form-item label="每条路线最多景点数"><el-input-number v-model="settings.max_spots" :min="1" :max="30" /></el-form-item>
        <el-form-item label="路线中可包含服务设施"><el-switch v-model="settings.include_service_points" /></el-form-item>
      </div>
      <el-button type="primary" :loading="saving" @click="saveSettings">保存设置</el-button>
    </section>

    <section class="data-section"><div class="data-section-header"><div><span>游客行程</span><h2>路线与评价</h2></div><strong>{{ routes.length }} 条</strong></div>
    <div class="filter-panel compact-filter">
      <el-input v-model="filters.interest" placeholder="按兴趣筛选" clearable />
      <el-select v-model="filters.rating" placeholder="按评分筛选" clearable>
        <el-option v-for="rating in 5" :key="rating" :label="`${rating} 星`" :value="rating" />
      </el-select>
      <el-button :loading="loading" @click="loadData">查询</el-button>
    </div>

    <el-table v-loading="loading" :data="routes" class="admin-table desktop-table">
      <el-table-column prop="id" label="行程编号" width="100" />
      <el-table-column prop="visitor_name" label="游客" min-width="110" />
      <el-table-column prop="interest" label="兴趣" min-width="130" />
      <el-table-column label="游览方式" width="110"><template #default="{ row }">{{ preferenceLabel(row.preference) }}</template></el-table-column>
      <el-table-column prop="spot_count" label="景点数" width="90" />
      <el-table-column label="时长" width="130">
        <template #default="{ row }">{{ row.total_duration_minutes }} / {{ row.duration_minutes }} 分钟</template>
      </el-table-column>
      <el-table-column prop="rating" label="评分" width="80" />
      <el-table-column prop="comment" label="反馈" min-width="180" show-overflow-tooltip />
      <el-table-column prop="created_at" label="生成时间" min-width="180" />
    </el-table>
    <div v-loading="loading" class="mobile-record-list"><article v-for="item in routes" :key="item.id" class="mobile-record-card"><header><div><span>行程 {{ item.id }}</span><h3>{{ item.interest }}</h3></div><el-tag v-if="item.rating" type="warning">{{ item.rating }} 星</el-tag><el-tag v-else type="info">未评价</el-tag></header><p>{{ item.visitor_name || '访客' }} · {{ item.spot_count }} 个景点 · {{ item.total_duration_minutes }}/{{ item.duration_minutes }} 分钟</p><p v-if="item.comment" class="record-comment">“{{ item.comment }}”</p><small>{{ new Date(item.created_at).toLocaleString('zh-CN') }}</small></article></div>
    <el-empty v-if="!loading && routes.length === 0" description="暂无游客行程" />
    </section>
  </AppLayout>
</template>
