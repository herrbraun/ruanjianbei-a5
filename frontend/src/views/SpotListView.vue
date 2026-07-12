<script setup lang="ts">
import { Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { getSpots, type ScenicSpot, type SpotType } from '@/api/spots'
import AppLayout from '@/layouts/AppLayout.vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const loading = ref(false)
const loadFailed = ref(false)
const spots = ref<ScenicSpot[]>([])
const failedImages = ref(new Set<number>())
const initialInterest = authStore.user?.interest?.split(/[,，、]/)[0]?.trim() || ''
const filters = reactive({ keyword: '', tag: initialInterest, scenic_area: '', spot_type: undefined as SpotType | undefined })
const activeFilters = computed(() => [filters.keyword, filters.tag, filters.scenic_area, filters.spot_type].filter(Boolean).length)

function typeLabel(type: SpotType) {
  return { attraction: '景点', area: '展区', service: '服务点' }[type]
}

async function loadSpots() {
  loading.value = true
  loadFailed.value = false
  try {
    spots.value = (await getSpots({ keyword: filters.keyword.trim() || undefined, tag: filters.tag.trim() || undefined, scenic_area: filters.scenic_area.trim() || undefined, spot_type: filters.spot_type })).data
  } catch {
    loadFailed.value = true
    ElMessage.error('景点加载失败，请检查网络后重试')
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.keyword = ''
  filters.tag = ''
  filters.scenic_area = ''
  filters.spot_type = undefined
  loadSpots()
}

function markImageFailed(id: number) {
  failedImages.value = new Set([...failedImages.value, id])
}

onMounted(loadSpots)
</script>

<template>
  <AppLayout title="景点浏览" description="浏览灵山胜境与拈花湾的景点和服务设施。" role-label="游览服务">
    <template #actions><RouterLink to="/visitor/routes"><el-button type="primary">生成路线</el-button></RouterLink></template>

    <section class="filter-panel" aria-label="景点筛选">
      <el-input v-model="filters.keyword" :prefix-icon="Search" placeholder="搜索名称、简介或位置" clearable @keyup.enter="loadSpots" />
      <el-input v-model="filters.tag" placeholder="兴趣标签" clearable @keyup.enter="loadSpots" />
      <el-select v-model="filters.scenic_area" placeholder="所属景区" clearable><el-option label="灵山胜境" value="灵山胜境" /><el-option label="拈花湾禅意小镇" value="拈花湾禅意小镇" /></el-select>
      <el-select v-model="filters.spot_type" placeholder="类型" clearable><el-option label="景点" value="attraction" /><el-option label="展区" value="area" /><el-option label="服务点" value="service" /></el-select>
      <el-button type="primary" :loading="loading" @click="loadSpots">查询</el-button>
      <el-button v-if="activeFilters" :icon="Refresh" text @click="resetFilters">重置</el-button>
    </section>

    <div class="result-toolbar"><span>共找到 <strong>{{ spots.length }}</strong> 个景点</span><span v-if="activeFilters">已启用 {{ activeFilters }} 项筛选</span></div>

    <div v-if="loading" class="spot-grid"><el-skeleton v-for="item in 6" :key="item" animated class="spot-skeleton"><template #template><el-skeleton-item variant="image" class="skeleton-image" /><div class="skeleton-body"><el-skeleton-item variant="h3" /><el-skeleton-item variant="text" /><el-skeleton-item variant="text" /></div></template></el-skeleton></div>
    <section v-else-if="spots.length" class="spot-grid" aria-live="polite">
      <article v-for="spot in spots" :key="spot.id" class="spot-card">
        <div class="spot-card-media">
          <img v-if="spot.cover_image_url && !failedImages.has(spot.id)" :src="spot.cover_image_url" :alt="spot.name" loading="lazy" @error="markImageFailed(spot.id)" />
          <div v-else class="spot-image-placeholder"><span>{{ spot.name.slice(0, 1) }}</span><small>{{ spot.scenic_area }}</small></div>
          <el-tag class="spot-type-tag" effect="dark" size="small">{{ typeLabel(spot.spot_type) }}</el-tag>
        </div>
        <div class="spot-card-body">
          <div class="spot-id-line"><span>{{ spot.external_id || `#${spot.id}` }}</span><span>{{ spot.recommended_duration_minutes }} 分钟</span></div>
          <h2>{{ spot.name }}</h2><p>{{ spot.summary }}</p>
          <div class="tag-row"><el-tag v-for="tag in spot.tags.slice(0, 4)" :key="tag" size="small" effect="plain">{{ tag }}</el-tag></div>
          <div class="spot-card-footer"><span>{{ spot.location || '位置待补充' }}</span><RouterLink class="text-link" :to="`/visitor/spots/${spot.id}`">查看详情</RouterLink></div>
        </div>
      </article>
    </section>
    <section v-else class="empty-panel"><el-empty :description="loadFailed ? '景点加载失败' : '暂无符合条件的景点'"><el-button v-if="loadFailed" type="primary" @click="loadSpots">重新加载</el-button><el-button v-else @click="resetFilters">清除筛选</el-button></el-empty></section>
  </AppLayout>
</template>
