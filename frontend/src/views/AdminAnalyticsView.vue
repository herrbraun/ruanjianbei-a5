<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  getAnalyticsOverview,
  getGuideDashboard,
  getRouteAnalytics,
  getSpotAnalytics,
  type AnalyticsOverview,
  type GuideDashboard,
  type RouteAnalytics,
  type SpotAnalytics,
} from '@/api/analytics'
import { knowledgeApi, type ScenicArea } from '@/api/knowledge'
import InsightChart from '@/components/InsightChart.vue'
import AppLayout from '@/layouts/AppLayout.vue'

const router = useRouter()
const loading = ref(false)
const scenicAreas = ref<ScenicArea[]>([])
const selectedScenicAreaId = ref<number>()
const overview = ref<AnalyticsOverview | null>(null)
const routeAnalytics = ref<RouteAnalytics | null>(null)
const spotAnalytics = ref<SpotAnalytics | null>(null)
const guideDashboard = ref<GuideDashboard | null>(null)

function dateText(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const today = new Date()
const weekAgo = new Date(today)
weekAgo.setDate(today.getDate() - 6)
const dateRange = ref<[string, string]>([dateText(weekAgo), dateText(today)])
const dateShortcuts = [
  { text: '今日', value: () => [new Date(), new Date()] },
  { text: '近 7 天', value: () => { const end = new Date(); const start = new Date(); start.setDate(start.getDate() - 6); return [start, end] } },
  { text: '近 30 天', value: () => { const end = new Date(); const start = new Date(); start.setDate(start.getDate() - 29); return [start, end] } },
]

const chartBase = {
  textStyle: { color: '#66736E', fontFamily: 'system-ui, Microsoft YaHei, sans-serif' },
  grid: { left: 24, right: 20, top: 28, bottom: 22, containLabel: true },
  tooltip: { trigger: 'axis', backgroundColor: '#17201D', borderWidth: 0, textStyle: { color: '#fff' } },
}

function percent(value: number) {
  return `${(value * 100).toFixed(1)}%`
}

function delta(current: number, previous: number, suffix = '') {
  if (!previous) return current ? '较上期新增' : '与上期持平'
  const change = ((current - previous) / previous) * 100
  return `${change >= 0 ? '↑' : '↓'} ${Math.abs(change).toFixed(1)}%${suffix}`
}

const guideCards = computed(() => {
  const current = guideDashboard.value?.metrics
  const previous = guideDashboard.value?.previous_period
  if (!current || !previous) return []
  const rows: Array<{ label: string; value: string | number; note: string; alert?: boolean }> = [
    { label: '服务游客', value: current.service_visitors, note: delta(current.service_visitors, previous.service_visitors) },
    { label: '导览会话', value: current.session_count, note: delta(current.session_count, previous.session_count) },
    { label: '游客提问', value: current.question_count, note: delta(current.question_count, previous.question_count) },
    { label: '回答成功率', value: percent(current.answer_success_rate), note: `上期 ${percent(previous.answer_success_rate)}` },
    { label: '平均响应', value: current.average_answer_duration_ms == null ? '暂无' : `${(current.average_answer_duration_ms / 1000).toFixed(1)}s`, note: '从提问到回答完成' },
    { label: '游客满意度', value: current.average_rating == null ? '暂无' : `${current.average_rating.toFixed(1)} / 5`, note: '来自游客主动评价' },
    { label: '负向反馈率', value: percent(current.negative_rate), note: `上期 ${percent(previous.negative_rate)}`, alert: current.negative_rate >= 0.2 },
    { label: '分析覆盖率', value: percent(current.analysis_coverage_rate), note: `${current.analysis_failed_count} 条待处理`, alert: current.analysis_failed_count > 0 },
  ]
  return rows
})

const serviceTrendOption = computed(() => ({
  ...chartBase,
  legend: { data: ['会话数', '游客数'], bottom: 0 },
  xAxis: { type: 'category', data: guideDashboard.value?.service_trend.map((item) => item.date) || [] },
  yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#EDF1EF' } } },
  series: [
    { name: '会话数', type: 'line', smooth: true, data: guideDashboard.value?.service_trend.map((item) => item.sessions) || [], lineStyle: { color: '#1F6D63', width: 3 }, itemStyle: { color: '#1F6D63' } },
    { name: '游客数', type: 'line', smooth: true, data: guideDashboard.value?.service_trend.map((item) => item.visitors) || [], lineStyle: { color: '#B8892D', width: 3 }, itemStyle: { color: '#B8892D' } },
  ],
}))

const sentimentOption = computed(() => ({
  ...chartBase,
  legend: { data: ['正向', '中性', '负向'], bottom: 0 },
  xAxis: { type: 'category', data: guideDashboard.value?.sentiment_trend.map((item) => item.date) || [] },
  yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#EDF1EF' } } },
  series: [
    { name: '正向', type: 'bar', stack: 'sentiment', data: guideDashboard.value?.sentiment_trend.map((item) => item.positive) || [], itemStyle: { color: '#4A9789' } },
    { name: '中性', type: 'bar', stack: 'sentiment', data: guideDashboard.value?.sentiment_trend.map((item) => item.neutral) || [], itemStyle: { color: '#C6CDC9' } },
    { name: '负向', type: 'bar', stack: 'sentiment', data: guideDashboard.value?.sentiment_trend.map((item) => item.negative) || [], itemStyle: { color: '#C45B4A' } },
  ],
}))

const topicOption = computed(() => ({
  ...chartBase,
  xAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#EDF1EF' } } },
  yAxis: { type: 'category', data: (guideDashboard.value?.topic_distribution || []).slice(0, 8).map((item) => item.name).reverse(), axisLine: { show: false }, axisTick: { show: false } },
  series: [{ type: 'bar', data: (guideDashboard.value?.topic_distribution || []).slice(0, 8).map((item) => item.count).reverse(), itemStyle: { color: '#1F6D63', borderRadius: [0, 5, 5, 0] }, barMaxWidth: 24 }],
}))

const satisfactionOption = computed(() => ({
  ...chartBase,
  xAxis: { type: 'category', data: guideDashboard.value?.satisfaction_trend.map((item) => item.date) || [] },
  yAxis: { type: 'value', min: 0, max: 5, splitLine: { lineStyle: { color: '#EDF1EF' } } },
  series: [{ type: 'line', smooth: true, data: guideDashboard.value?.satisfaction_trend.map((item) => item.average_rating) || [], lineStyle: { color: '#B8892D', width: 3 }, itemStyle: { color: '#B8892D' }, areaStyle: { color: 'rgba(184,137,45,.1)' } }],
}))

const routeTrendOption = computed(() => ({ ...chartBase, xAxis: { type: 'category', data: routeAnalytics.value?.daily_routes.map((item) => item.date) || [] }, yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#EDF1EF' } } }, series: [{ type: 'line', smooth: true, data: routeAnalytics.value?.daily_routes.map((item) => item.count) || [], lineStyle: { color: '#1F6D63', width: 3 }, itemStyle: { color: '#B8892D' } }] }))
const spotOption = computed(() => { const rows = (spotAnalytics.value?.route_popular_spots || []).filter((item) => item.selected_count > 0).slice(0, 8).reverse(); return { ...chartBase, xAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#EDF1EF' } } }, yAxis: { type: 'category', data: rows.map((item) => item.name), axisLine: { show: false }, axisTick: { show: false } }, series: [{ type: 'bar', data: rows.map((item) => item.selected_count), itemStyle: { color: '#B8892D', borderRadius: [0, 4, 4, 0] }, barMaxWidth: 22 }] } })

async function loadAnalytics() {
  if (!selectedScenicAreaId.value) return
  loading.value = true
  try {
    const [overviewResponse, routesResponse, spotsResponse, guideResponse] = await Promise.all([
      getAnalyticsOverview(), getRouteAnalytics(), getSpotAnalytics(),
      getGuideDashboard(selectedScenicAreaId.value, dateRange.value[0], dateRange.value[1]),
    ])
    overview.value = overviewResponse.data
    routeAnalytics.value = routesResponse.data
    spotAnalytics.value = spotsResponse.data
    guideDashboard.value = guideResponse.data
  } catch {
    ElMessage.error('运营统计加载失败，请检查服务后重试')
  } finally {
    loading.value = false
  }
}

async function initialize() {
  try {
    scenicAreas.value = (await knowledgeApi.listScenicAreas()).data
    selectedScenicAreaId.value = scenicAreas.value[0]?.id
    await loadAnalytics()
  } catch {
    ElMessage.error('景区列表加载失败')
  }
}

function openInsights() {
  router.push({ path: '/admin/insights', query: selectedScenicAreaId.value ? { scenic_area_id: selectedScenicAreaId.value } : undefined })
}

onMounted(initialize)
</script>

<template>
  <AppLayout title="游客感受度大屏" description="从服务规模、回答质量、游客情绪和主动评价观察数字导览体验。" role-label="运营管理">
    <template #actions><el-button :icon="Refresh" :loading="loading" @click="loadAnalytics">刷新</el-button></template>

    <section class="analytics-filter-bar">
      <el-select v-model="selectedScenicAreaId" placeholder="选择景区" @change="loadAnalytics">
        <el-option v-for="area in scenicAreas" :key="area.id" :label="area.name" :value="area.id" />
      </el-select>
      <el-date-picker v-model="dateRange" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" :shortcuts="dateShortcuts" :clearable="false" @change="loadAnalytics" />
      <el-button type="primary" plain @click="openInsights">查看报告与风险事项</el-button>
    </section>

    <section v-loading="loading" class="analytics-grid guide-metric-grid">
      <article v-for="card in guideCards" :key="card.label" class="metric-card" :class="{ 'is-alert': card.alert }">
        <span>{{ card.label }}</span><strong>{{ card.value }}</strong><small>{{ card.note }}</small>
      </article>
    </section>

    <section class="analytics-section">
      <div class="data-section-header"><div><span>数字导览趋势</span><h2>服务量与游客感受</h2><p>情绪由模型按固定标签分析，满意度来自游客主动提交的 1–5 分评价。</p></div></div>
      <div class="chart-grid">
        <article class="chart-panel"><h3>服务量趋势</h3><InsightChart :option="serviceTrendOption" :empty="!guideDashboard?.service_trend.length" empty-text="该时段暂无导览会话" summary="按日期展示会话数和独立游客数" /></article>
        <article class="chart-panel"><h3>情绪趋势</h3><InsightChart :option="sentimentOption" :empty="!guideDashboard?.sentiment_trend.length" empty-text="完成互动分析后显示情绪趋势" summary="按日期堆叠展示正向、中性和负向互动" /></article>
        <article class="chart-panel"><h3>咨询主题分布</h3><InsightChart :option="topicOption" :empty="!guideDashboard?.topic_distribution.length" empty-text="暂无主题分析数据" summary="展示游客最常咨询的主题" /></article>
        <article class="chart-panel"><h3>满意度趋势</h3><InsightChart :option="satisfactionOption" :empty="!guideDashboard?.satisfaction_trend.length" empty-text="游客提交评价后显示趋势" summary="按日期展示游客平均满意度" /></article>
      </div>
    </section>

    <section class="analytics-table-grid">
      <article class="analytics-table-panel"><div class="data-section-header compact"><div><span>高频诉求</span><h2>热门问题</h2></div></div><el-table :data="guideDashboard?.popular_questions || []" empty-text="暂无热门问题"><el-table-column type="index" width="56" label="#" /><el-table-column prop="name" label="归一化问题" /><el-table-column prop="count" label="次数" width="90" /></el-table></article>
      <article class="analytics-table-panel"><div class="data-section-header compact"><div><span>服务风险</span><h2>待关注事项</h2></div><el-button text type="primary" @click="openInsights">查看全部</el-button></div><el-table :data="guideDashboard?.attention_preview || []" empty-text="暂无待关注事项"><el-table-column prop="normalized_question" label="问题" /><el-table-column prop="issue_type" label="类型" width="120" /><el-table-column prop="sentiment" label="情绪" width="80" /></el-table></article>
    </section>

    <section class="analytics-section secondary-analytics">
      <div class="data-section-header"><div><span>全局运营概览</span><h2>路线与景点使用情况</h2><p v-if="overview">共生成 {{ overview.route_count }} 条路线，记录 {{ overview.behavior_record_count }} 次游览行为。</p></div></div>
      <div class="chart-grid">
        <article class="chart-panel"><h3>路线生成趋势</h3><InsightChart :option="routeTrendOption" :empty="!routeAnalytics?.daily_routes.length" empty-text="生成路线后显示趋势" summary="按日期展示路线生成次数" /></article>
        <article class="chart-panel"><h3>热门推荐景点</h3><InsightChart :option="spotOption" :empty="!spotAnalytics?.route_popular_spots.some((item) => item.selected_count > 0)" empty-text="暂无景点推荐数据" summary="展示路线中入选次数最多的景点" /></article>
      </div>
    </section>
  </AppLayout>
</template>
