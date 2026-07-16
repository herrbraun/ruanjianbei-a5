<script setup lang="ts">
import { ElMessage } from 'element-plus'
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
  <AppLayout title="路线与反馈" description="调整推荐设置，查看游客行程与评价。" role-label="运营管理">
    <section class="settings-panel">
      <div class="data-section-header"><div><span>推荐设置</span><h2>路线偏好</h2><p>修改后将应用于新生成的路线。</p></div><el-tag type="success" effect="plain">已启用</el-tag></div>
      <div class="form-grid">
        <el-form-item label="兴趣匹配权重"><el-input-number v-model="settings.tag_match_weight" :min="0" :max="1000" /></el-form-item>
        <el-form-item label="景点优先级权重"><el-input-number v-model="settings.priority_weight" :min="0" :max="100" :step="0.1" /></el-form-item>
        <el-form-item label="单条路线景点上限"><el-input-number v-model="settings.max_spots" :min="1" :max="30" /></el-form-item>
        <el-form-item label="允许推荐服务点"><el-switch v-model="settings.include_service_points" /></el-form-item>
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
      <el-table-column prop="id" label="路线 ID" width="90" />
      <el-table-column prop="visitor_name" label="游客" min-width="110" />
      <el-table-column prop="interest" label="兴趣" min-width="130" />
      <el-table-column prop="preference" label="偏好" width="110" />
      <el-table-column prop="spot_count" label="景点数" width="90" />
      <el-table-column label="时长" width="130">
        <template #default="{ row }">{{ row.total_duration_minutes }} / {{ row.duration_minutes }} 分钟</template>
      </el-table-column>
      <el-table-column prop="rating" label="评分" width="80" />
      <el-table-column prop="comment" label="反馈" min-width="180" show-overflow-tooltip />
      <el-table-column prop="created_at" label="生成时间" min-width="180" />
    </el-table>
    <div v-loading="loading" class="mobile-record-list"><article v-for="item in routes" :key="item.id" class="mobile-record-card"><header><div><span>路线 #{{ item.id }}</span><h3>{{ item.interest }}</h3></div><el-tag v-if="item.rating" type="warning">{{ item.rating }} 星</el-tag><el-tag v-else type="info">未反馈</el-tag></header><p>{{ item.visitor_name || '匿名游客' }} · {{ item.spot_count }} 个景点 · {{ item.total_duration_minutes }}/{{ item.duration_minutes }} 分钟</p><p v-if="item.comment" class="record-comment">“{{ item.comment }}”</p><small>{{ new Date(item.created_at).toLocaleString('zh-CN') }}</small></article></div>
    <el-empty v-if="!loading && routes.length === 0" description="暂无游客行程" />
    </section>
  </AppLayout>
</template>
