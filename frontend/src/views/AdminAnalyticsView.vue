<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

import { getAnalyticsOverview, getRouteAnalytics, getSpotAnalytics, type AnalyticsOverview, type RouteAnalytics, type SpotAnalytics } from '@/api/analytics'
import InsightChart from '@/components/InsightChart.vue'
import AppLayout from '@/layouts/AppLayout.vue'

const loading = ref(false)
const overview = ref<AnalyticsOverview | null>(null)
const routeAnalytics = ref<RouteAnalytics | null>(null)
const spotAnalytics = ref<SpotAnalytics | null>(null)
const chartBase = { textStyle: { color: '#66736E', fontFamily: 'system-ui, Microsoft YaHei, sans-serif' }, grid: { left: 24, right: 20, top: 24, bottom: 20, containLabel: true }, tooltip: { trigger: 'axis', backgroundColor: '#17201D', borderWidth: 0, textStyle: { color: '#fff' } } }

const cards = computed(() => overview.value ? [
  { label: '景点总数', value: overview.value.spot_count, note: `${overview.value.enabled_spot_count} 个已启用` },
  { label: '路线生成', value: overview.value.route_count, note: `${overview.value.feedback_count} 条反馈` },
  { label: '路线评分', value: overview.value.average_rating ?? '暂无', note: '满分 5 分' },
  { label: '游览次数', value: overview.value.behavior_record_count, note: `${overview.value.behavior_visitor_count} 位游客` },
  { label: '游览满意度', value: overview.value.behavior_average_satisfaction ?? '暂无', note: '满分 5 分' },
  { label: '素材数量', value: overview.value.media_count, note: '已录入素材' },
] : [])

const routeTrendOption = computed(() => ({ ...chartBase, xAxis: { type: 'category', data: routeAnalytics.value?.daily_routes.map((item) => item.date) || [], axisLine: { lineStyle: { color: '#D9E0DC' } } }, yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#EDF1EF' } } }, series: [{ type: 'line', smooth: true, symbolSize: 8, data: routeAnalytics.value?.daily_routes.map((item) => item.count) || [], lineStyle: { color: '#1F6D63', width: 3 }, itemStyle: { color: '#B8892D' }, areaStyle: { color: 'rgba(31,109,99,.08)' } }] }))
const interestOption = computed(() => ({ ...chartBase, xAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#EDF1EF' } } }, yAxis: { type: 'category', data: routeAnalytics.value?.popular_interests.map((item) => item.name).reverse() || [], axisLine: { show: false }, axisTick: { show: false } }, series: [{ type: 'bar', data: routeAnalytics.value?.popular_interests.map((item) => item.count).reverse() || [], barMaxWidth: 22, itemStyle: { color: '#1F6D63', borderRadius: [0, 4, 4, 0] }, label: { show: true, position: 'right', color: '#17201D' } }] }))
const spotOption = computed(() => { const rows = (spotAnalytics.value?.route_popular_spots || []).filter((item) => item.selected_count > 0).slice(0, 8).reverse(); return { ...chartBase, xAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#EDF1EF' } } }, yAxis: { type: 'category', data: rows.map((item) => item.name), axisLine: { show: false }, axisTick: { show: false } }, series: [{ type: 'bar', data: rows.map((item) => item.selected_count), barMaxWidth: 22, itemStyle: { color: '#B8892D', borderRadius: [0, 4, 4, 0] }, label: { show: true, position: 'right', color: '#17201D' } }] } })
const behaviorOption = computed(() => ({ ...chartBase, legend: { data: ['平均停留小时', '平均满意度'], bottom: 0 }, xAxis: { type: 'category', data: spotAnalytics.value?.behavior_attractions.map((item) => item.name) || [], axisLabel: { interval: 0 } }, yAxis: { type: 'value', splitLine: { lineStyle: { color: '#EDF1EF' } } }, series: [{ name: '平均停留小时', type: 'bar', data: spotAnalytics.value?.behavior_attractions.map((item) => item.average_stay_hours) || [], itemStyle: { color: '#1F6D63' }, barMaxWidth: 26 }, { name: '平均满意度', type: 'bar', data: spotAnalytics.value?.behavior_attractions.map((item) => item.average_satisfaction) || [], itemStyle: { color: '#B8892D' }, barMaxWidth: 26 }] }))

async function loadAnalytics() {
  loading.value = true
  try {
    const [overviewResponse, routesResponse, spotsResponse] = await Promise.all([getAnalyticsOverview(), getRouteAnalytics(), getSpotAnalytics()])
    overview.value = overviewResponse.data; routeAnalytics.value = routesResponse.data; spotAnalytics.value = spotsResponse.data
  } catch { ElMessage.error('运营统计加载失败，请检查服务后重试') }
  finally { loading.value = false }
}

onMounted(loadAnalytics)
</script>

<template>
  <AppLayout title="运营统计" description="查看路线使用、游客反馈和景点热度。" role-label="运营管理">
    <template #actions><el-button :icon="Refresh" :loading="loading" @click="loadAnalytics">刷新</el-button></template>
    <section v-loading="loading" class="analytics-grid"><article v-for="card in cards" :key="card.label" class="metric-card"><span>{{ card.label }}</span><strong>{{ card.value }}</strong><small>{{ card.note }}</small></article></section>

    <section class="analytics-section"><div class="data-section-header"><div><span>路线运营</span><h2>推荐与反馈表现</h2><p v-if="routeAnalytics">反馈率 {{ (routeAnalytics.feedback_rate * 100).toFixed(1) }}%，平均规划 {{ routeAnalytics.average_planned_minutes ?? 0 }} 分钟。</p></div></div>
      <div class="chart-grid"><article class="chart-panel"><h3>路线生成趋势</h3><InsightChart :option="routeTrendOption" :empty="!routeAnalytics?.daily_routes.length" empty-text="生成路线后将在此显示趋势" summary="按日期展示路线生成次数" /></article><article class="chart-panel"><h3>热门兴趣</h3><InsightChart :option="interestOption" :empty="!routeAnalytics?.popular_interests.length" empty-text="暂无游客兴趣数据" summary="展示生成路线时最常见的兴趣" /></article></div>
      <details v-if="routeAnalytics?.popular_interests.length" class="table-disclosure"><summary>查看路线统计表</summary><el-table :data="routeAnalytics.popular_interests" class="admin-table"><el-table-column prop="name" label="兴趣" /><el-table-column prop="count" label="路线次数" /></el-table></details>
    </section>

    <section class="analytics-section"><div class="data-section-header"><div><span>景点表现</span><h2>推荐热度与游览情况</h2></div></div>
      <div class="chart-grid"><article class="chart-panel"><h3>路线热门景点</h3><InsightChart :option="spotOption" :empty="!spotAnalytics?.route_popular_spots.some((item) => item.selected_count > 0)" empty-text="暂无景点推荐数据" summary="展示路线中被推荐次数最多的景点" /></article><article class="chart-panel"><h3>景区游览对比</h3><InsightChart :option="behaviorOption" :empty="!spotAnalytics?.behavior_attractions.length" empty-text="暂无游览统计" summary="对比各景区的平均停留时长和满意度" /></article></div>
      <details v-if="spotAnalytics?.behavior_attractions.length" class="table-disclosure"><summary>查看详细数据</summary><el-table :data="spotAnalytics.behavior_attractions" class="admin-table"><el-table-column prop="name" label="景区" /><el-table-column prop="visits" label="游览次数" /><el-table-column prop="unique_visitors" label="游客数" /><el-table-column prop="average_stay_hours" label="平均停留小时" /><el-table-column prop="average_cost" label="平均消费" /><el-table-column prop="average_satisfaction" label="平均满意度" /></el-table></details>
    </section>
  </AppLayout>
</template>
