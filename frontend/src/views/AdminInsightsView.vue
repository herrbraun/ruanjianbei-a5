<script setup lang="ts">
import { Clock, Download, Printer, Refresh, Warning } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { insightsApi, type InsightMessage, type InsightReport, type InsightReportSchedule } from '@/api/insights'
import { knowledgeApi, type ScenicArea } from '@/api/knowledge'
import AppLayout from '@/layouts/AppLayout.vue'

const route = useRoute()
const activeTab = ref<'reports' | 'risks'>('reports')
const scenicAreas = ref<ScenicArea[]>([])
const selectedScenicAreaId = ref<number>()
const loadingReports = ref(false)
const generatingReport = ref(false)
const savingSchedule = ref(false)
const exportingReport = ref(false)
const REPORT_POLL_LIMIT = 100
const reports = ref<InsightReport[]>([])
const selectedReport = ref<InsightReport | null>(null)
const schedule = ref<InsightReportSchedule | null>(null)
const loadingRisks = ref(false)
const retryingFailed = ref(false)
const risks = ref<InsightMessage[]>([])
const riskTotal = ref(0)
const riskPage = ref(1)
const reportType = ref<'daily' | 'weekly'>('weekly')
let reportPollTimer: ReturnType<typeof setTimeout> | undefined

function dateText(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const today = new Date()
const weekAgo = new Date(today)
weekAgo.setDate(today.getDate() - 6)
const reportRange = ref<[string, string]>([dateText(weekAgo), dateText(today)])
const riskRange = ref<[string, string]>([dateText(weekAgo), dateText(today)])
const dateShortcuts = [
  { text: '今日', value: () => [new Date(), new Date()] },
  { text: '近 7 天', value: () => { const end = new Date(); const start = new Date(); start.setDate(start.getDate() - 6); return [start, end] } },
  { text: '近 30 天', value: () => { const end = new Date(); const start = new Date(); start.setDate(start.getDate() - 29); return [start, end] } },
]

const riskFilters = reactive({
  sentiment: '' as '' | 'positive' | 'neutral' | 'negative',
  issue_type: '',
  analysis_status: '',
  resolution_status: 'unresolved',
  needs_attention: true as boolean | undefined,
})

const issueTypes = ['排队时间', '路线指引', '价格问题', '环境卫生', '工作人员服务', '数字人回答不准确', '响应速度', '语音或数字人体验', '设施问题', '无明确问题']
const weekdayOptions = [
  { label: '周一', value: 0 }, { label: '周二', value: 1 }, { label: '周三', value: 2 },
  { label: '周四', value: 3 }, { label: '周五', value: 4 }, { label: '周六', value: 5 },
  { label: '周日', value: 6 },
]
const currentScenicName = computed(() => scenicAreas.value.find((item) => item.id === selectedScenicAreaId.value)?.name || '当前景区')

function errorText(error: unknown, fallback: string) {
  return (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || fallback
}

function reportStatusText(status: InsightReport['generation_status']) {
  return { pending: '等待生成', processing: '生成中', completed: '已完成', failed: '生成失败' }[status]
}

function analysisStatusText(status: InsightMessage['analysis_status']) {
  return { pending: '待分析', processing: '分析中', completed: '已完成', failed: '分析失败' }[status]
}

function sentimentText(value: InsightMessage['sentiment']) {
  return value ? { positive: '正向', neutral: '中性', negative: '负向' }[value] : '未分析'
}

async function loadReports(selectId?: number) {
  if (!selectedScenicAreaId.value) return
  loadingReports.value = true
  try {
    reports.value = (await insightsApi.listReports(selectedScenicAreaId.value)).data
    const id = selectId || selectedReport.value?.id
    selectedReport.value = reports.value.find((item) => item.id === id) || reports.value[0] || null
  } catch (error) {
    ElMessage.error(errorText(error, '报告列表加载失败'))
  } finally {
    loadingReports.value = false
  }
}

async function refreshSelectedReport() {
  if (!selectedReport.value) return
  try {
    selectedReport.value = (await insightsApi.getReport(selectedReport.value.id)).data
    const index = reports.value.findIndex((item) => item.id === selectedReport.value?.id)
    if (index >= 0) reports.value[index] = selectedReport.value
  } catch (error) {
    ElMessage.error(errorText(error, '报告状态刷新失败'))
  }
}

async function loadSchedule() {
  if (!selectedScenicAreaId.value) return
  try {
    schedule.value = (await insightsApi.getSchedule(selectedScenicAreaId.value)).data
  } catch (error) {
    ElMessage.error(errorText(error, '自动报告配置加载失败'))
  }
}

async function saveSchedule() {
  if (!selectedScenicAreaId.value || !schedule.value) return
  savingSchedule.value = true
  try {
    schedule.value = (await insightsApi.updateSchedule(selectedScenicAreaId.value, {
      daily_enabled: schedule.value.daily_enabled,
      daily_run_time: schedule.value.daily_run_time,
      weekly_enabled: schedule.value.weekly_enabled,
      weekly_weekday: schedule.value.weekly_weekday,
      weekly_run_time: schedule.value.weekly_run_time,
      timezone: schedule.value.timezone,
    })).data
    ElMessage.success('自动报告计划已保存')
  } catch (error) {
    ElMessage.error(errorText(error, '自动报告计划保存失败'))
  } finally {
    savingSchedule.value = false
  }
}

async function exportSelectedReport() {
  if (!selectedReport.value || selectedReport.value.generation_status !== 'completed') return
  exportingReport.value = true
  try {
    const response = await insightsApi.exportReport(selectedReport.value.id)
    const url = URL.createObjectURL(response.data)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${currentScenicName.value}游客感受度${selectedReport.value.period_type === 'daily' ? '日报' : '周报'}-${selectedReport.value.period_start}-${selectedReport.value.period_end}.docx`
    anchor.style.display = 'none'
    document.body.appendChild(anchor)
    anchor.click()
    window.setTimeout(() => {
      anchor.remove()
      URL.revokeObjectURL(url)
    }, 1000)
  } catch (error) {
    ElMessage.error(errorText(error, '报告导出失败'))
  } finally {
    exportingReport.value = false
  }
}

function printSelectedReport() {
  if (selectedReport.value?.generation_status !== 'completed') return
  window.print()
}

async function retrySelectedReport() {
  if (!selectedReport.value) return
  try {
    const report = (await insightsApi.retryReport(selectedReport.value.id)).data
    selectedReport.value = report
    const index = reports.value.findIndex((item) => item.id === report.id)
    if (index >= 0) reports.value[index] = report
    scheduleReportPoll(report.id)
    ElMessage.success('报告已重新加入生成队列')
  } catch (error) {
    ElMessage.error(errorText(error, '报告重试失败'))
  }
}

function scheduleReportPoll(reportId: number, attempt = 0) {
  if (reportPollTimer) clearTimeout(reportPollTimer)
  if (attempt >= REPORT_POLL_LIMIT) {
    ElMessage.warning('报告仍在后台生成，可稍后点击“刷新报告状态”查看结果')
    return
  }
  reportPollTimer = setTimeout(async () => {
    try {
      const report = (await insightsApi.getReport(reportId)).data
      selectedReport.value = report
      const index = reports.value.findIndex((item) => item.id === report.id)
      if (index >= 0) reports.value[index] = report
      if (report.generation_status === 'pending' || report.generation_status === 'processing') scheduleReportPoll(reportId, attempt + 1)
    } catch {
      scheduleReportPoll(reportId, attempt + 1)
    }
  }, 1500)
}

async function createReport() {
  if (!selectedScenicAreaId.value) return
  generatingReport.value = true
  try {
    const report = (await insightsApi.createReport({
      scenic_area_id: selectedScenicAreaId.value,
      period_type: reportType.value,
      period_start: reportRange.value[0],
      period_end: reportRange.value[1],
    })).data
    if (!reports.value.some((item) => item.id === report.id)) reports.value.unshift(report)
    selectedReport.value = report
    ElMessage.success('报告任务已创建，正在生成')
    scheduleReportPoll(report.id)
  } catch (error) {
    ElMessage.error(errorText(error, '报告创建失败'))
  } finally {
    generatingReport.value = false
  }
}

async function loadRisks() {
  if (!selectedScenicAreaId.value) return
  loadingRisks.value = true
  try {
    const { data } = await insightsApi.listMessages({
      scenic_area_id: selectedScenicAreaId.value,
      sentiment: riskFilters.sentiment || undefined,
      issue_type: riskFilters.issue_type || undefined,
      analysis_status: riskFilters.analysis_status || undefined,
      resolution_status: riskFilters.resolution_status || undefined,
      needs_attention: riskFilters.needs_attention,
      start_date: riskRange.value[0],
      end_date: riskRange.value[1],
      page: riskPage.value,
      page_size: 20,
    })
    risks.value = data.items
    riskTotal.value = data.total
  } catch (error) {
    ElMessage.error(errorText(error, '风险事项加载失败'))
  } finally {
    loadingRisks.value = false
  }
}

function applyRiskFilters() {
  riskPage.value = 1
  void loadRisks()
}

async function retryInsight(row: InsightMessage) {
  try {
    await insightsApi.retry(row.id)
    row.analysis_status = 'pending'
    row.error_message = null
    ElMessage.success('已重新加入分析队列')
  } catch (error) {
    ElMessage.error(errorText(error, '重试失败'))
  }
}

async function retryAllFailed() {
  if (!selectedScenicAreaId.value) return
  retryingFailed.value = true
  try {
    const { data } = await insightsApi.retryFailed(selectedScenicAreaId.value)
    const scheduled = (data as { scheduled?: number }).scheduled || 0
    ElMessage.success(`已安排 ${scheduled} 条记录重试`)
    await loadRisks()
  } catch (error) {
    ElMessage.error(errorText(error, '批量重试失败'))
  } finally {
    retryingFailed.value = false
  }
}

async function toggleResolved(row: InsightMessage) {
  try {
    const resolved = row.resolution_status !== 'resolved'
    await insightsApi.resolve(row.id, resolved)
    row.resolution_status = resolved ? 'resolved' : 'unresolved'
    if (riskFilters.resolution_status === 'unresolved' && resolved) await loadRisks()
  } catch (error) {
    ElMessage.error(errorText(error, '处理状态更新失败'))
  }
}

async function onScenicChange() {
  riskPage.value = 1
  selectedReport.value = null
  await Promise.all([loadReports(), loadRisks(), loadSchedule()])
}

async function initialize() {
  try {
    scenicAreas.value = (await knowledgeApi.listScenicAreas()).data
    const requested = Number(route.query.scenic_area_id)
    selectedScenicAreaId.value = scenicAreas.value.some((item) => item.id === requested) ? requested : scenicAreas.value[0]?.id
    await Promise.all([loadReports(), loadRisks(), loadSchedule()])
  } catch (error) {
    ElMessage.error(errorText(error, '游客洞察工作台初始化失败'))
  }
}

watch(reportType, (type) => {
  const end = new Date()
  const start = new Date(end)
  if (type === 'weekly') start.setDate(end.getDate() - 6)
  reportRange.value = [dateText(start), dateText(end)]
})

onMounted(initialize)
onBeforeUnmount(() => { if (reportPollTimer) clearTimeout(reportPollTimer) })
</script>

<template>
  <AppLayout title="游客洞察" description="生成景区感受度报告，跟进负向反馈、服务风险和分析失败记录。" role-label="运营管理">
    <template #actions><el-button :icon="Refresh" @click="activeTab === 'reports' ? loadReports() : loadRisks()">刷新</el-button></template>

    <section class="insights-toolbar">
      <el-select v-model="selectedScenicAreaId" placeholder="选择景区" @change="onScenicChange"><el-option v-for="area in scenicAreas" :key="area.id" :label="area.name" :value="area.id" /></el-select>
      <span>{{ currentScenicName }}</span>
    </section>

    <el-tabs v-model="activeTab" class="insights-tabs">
      <el-tab-pane label="感受度报告" name="reports">
        <section class="report-create-bar">
          <el-radio-group v-model="reportType"><el-radio-button value="daily">日报</el-radio-button><el-radio-button value="weekly">周报</el-radio-button></el-radio-group>
          <el-date-picker v-model="reportRange" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" :shortcuts="dateShortcuts" :clearable="false" />
          <el-button type="primary" :loading="generatingReport" @click="createReport">生成报告</el-button>
        </section>

        <section v-if="schedule" class="report-schedule-card">
          <header>
            <div><span><Clock /> AUTOMATION</span><h2>自动报告计划</h2></div>
            <small>按 Asia/Shanghai 生成上一完整周期，服务重启后会自动补偿遗漏任务。</small>
          </header>
          <div class="report-schedule-grid">
            <article>
              <el-switch v-model="schedule.daily_enabled" active-text="每日自动生成" />
              <label>生成时间<el-time-picker v-model="schedule.daily_run_time" value-format="HH:mm:ss" format="HH:mm" :disabled="!schedule.daily_enabled" /></label>
              <p>默认生成上一自然日的游客感受度日报。</p>
            </article>
            <article>
              <el-switch v-model="schedule.weekly_enabled" active-text="每周自动生成" />
              <label>生成日<el-select v-model="schedule.weekly_weekday" :disabled="!schedule.weekly_enabled"><el-option v-for="item in weekdayOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></label>
              <label>生成时间<el-time-picker v-model="schedule.weekly_run_time" value-format="HH:mm:ss" format="HH:mm" :disabled="!schedule.weekly_enabled" /></label>
              <p>生成执行日前连续七天的完整周报。</p>
            </article>
          </div>
          <footer><span>时区：{{ schedule.timezone }}</span><el-button type="primary" plain :loading="savingSchedule" @click="saveSchedule">保存自动计划</el-button></footer>
        </section>

        <div class="report-workspace" v-loading="loadingReports">
          <aside class="report-list">
            <button v-for="report in reports" :key="report.id" type="button" :class="{ active: selectedReport?.id === report.id }" @click="selectedReport = report">
              <strong>{{ report.period_start }} 至 {{ report.period_end }}</strong>
              <span>{{ report.period_type === 'daily' ? '日报' : '周报' }} · {{ reportStatusText(report.generation_status) }}</span>
            </button>
            <el-empty v-if="!reports.length" description="尚未生成报告" :image-size="72" />
          </aside>

          <article v-if="selectedReport" class="report-detail">
            <header><div><span>{{ selectedReport.period_type === 'daily' ? '游客感受度日报' : '游客感受度周报' }} · {{ selectedReport.trigger_source === 'scheduled' ? '自动生成' : '手动生成' }}</span><h2>{{ selectedReport.period_start }} 至 {{ selectedReport.period_end }}</h2></div><div class="report-detail-actions"><el-tag :type="selectedReport.generation_status === 'failed' ? 'danger' : selectedReport.generation_status === 'completed' ? 'success' : 'warning'">{{ reportStatusText(selectedReport.generation_status) }}</el-tag><el-button :icon="Download" :loading="exportingReport" :disabled="selectedReport.generation_status !== 'completed'" @click="exportSelectedReport">导出 Word</el-button><el-button :icon="Printer" :disabled="selectedReport.generation_status !== 'completed'" @click="printSelectedReport">打印 / PDF</el-button></div></header>
            <div v-if="selectedReport.generation_status === 'pending' || selectedReport.generation_status === 'processing'" class="report-waiting"><el-icon class="is-loading"><Refresh /></el-icon><p>模型正在根据聚合统计生成报告，不会传入游客身份信息。</p></div>
            <div v-else-if="selectedReport.generation_status === 'failed'" class="report-failed"><el-alert type="error" :closable="false" title="报告生成失败"><template #default>{{ selectedReport.error_message || '可稍后重试。' }}</template></el-alert><el-button type="primary" plain :icon="Refresh" @click="retrySelectedReport">重新生成</el-button></div>
            <template v-else>
              <section><h3>总体结论</h3><p>{{ selectedReport.summary }}</p></section>
              <section><h3>重点关注</h3><ul><li v-for="item in selectedReport.attention_points || []" :key="item">{{ item }}</li></ul></section>
              <section><h3>风险发现</h3><ul><li v-for="item in selectedReport.risk_findings || []" :key="item">{{ item }}</li></ul></section>
              <section><h3>改进建议</h3><ol><li v-for="item in selectedReport.recommendations || []" :key="item">{{ item }}</li></ol></section>
            </template>
            <el-button text :icon="Refresh" @click="refreshSelectedReport">刷新报告状态</el-button>
          </article>
          <el-empty v-else class="report-detail" description="选择或生成一份报告" />
        </div>
      </el-tab-pane>

      <el-tab-pane label="风险与待办" name="risks">
        <section class="risk-filter-bar">
          <el-date-picker v-model="riskRange" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" :shortcuts="dateShortcuts" :clearable="false" @change="applyRiskFilters" />
          <el-select v-model="riskFilters.sentiment" clearable placeholder="全部情绪" @change="applyRiskFilters"><el-option label="正向" value="positive" /><el-option label="中性" value="neutral" /><el-option label="负向" value="negative" /></el-select>
          <el-select v-model="riskFilters.issue_type" clearable placeholder="全部问题类型" @change="applyRiskFilters"><el-option v-for="item in issueTypes" :key="item" :label="item" :value="item" /></el-select>
          <el-select v-model="riskFilters.analysis_status" clearable placeholder="全部分析状态" @change="applyRiskFilters"><el-option label="待分析" value="pending" /><el-option label="分析中" value="processing" /><el-option label="已完成" value="completed" /><el-option label="分析失败" value="failed" /></el-select>
          <el-select v-model="riskFilters.resolution_status" clearable placeholder="全部处理状态" @change="applyRiskFilters"><el-option label="待处理" value="unresolved" /><el-option label="已解决" value="resolved" /></el-select>
          <el-checkbox v-model="riskFilters.needs_attention" :true-value="true" :false-value="undefined" @change="applyRiskFilters">仅需关注</el-checkbox>
          <el-button :icon="Refresh" :loading="retryingFailed" @click="retryAllFailed">重试失败分析</el-button>
        </section>

        <el-table v-loading="loadingRisks" :data="risks" class="admin-table" row-key="id" empty-text="暂无符合条件的记录">
          <el-table-column type="expand"><template #default="{ row }: { row: InsightMessage }"><div class="insight-dialogue-detail"><strong>游客原始问题</strong><p>{{ row.question || '无' }}</p><strong>数字人回答</strong><p>{{ row.answer || '无' }}</p><small v-if="row.error_message">分析诊断：{{ row.error_message }}</small></div></template></el-table-column>
          <el-table-column label="游客问题摘要" min-width="220"><template #default="{ row }: { row: InsightMessage }"><strong>{{ row.normalized_question || '待分析' }}</strong></template></el-table-column>
          <el-table-column prop="primary_topic" label="主题" width="120" />
          <el-table-column label="情绪" width="90"><template #default="{ row }: { row: InsightMessage }"><el-tag :type="row.sentiment === 'negative' ? 'danger' : row.sentiment === 'positive' ? 'success' : 'info'">{{ sentimentText(row.sentiment) }}</el-tag></template></el-table-column>
          <el-table-column prop="issue_type" label="问题类型" width="150" />
          <el-table-column label="分析状态" width="110"><template #default="{ row }: { row: InsightMessage }">{{ analysisStatusText(row.analysis_status) }}</template></el-table-column>
          <el-table-column label="操作" width="190" fixed="right"><template #default="{ row }: { row: InsightMessage }"><el-button v-if="row.analysis_status === 'failed' || row.analysis_status === 'pending'" text type="primary" @click="retryInsight(row)">重试</el-button><el-button text :type="row.resolution_status === 'resolved' ? 'info' : 'success'" @click="toggleResolved(row)">{{ row.resolution_status === 'resolved' ? '重新打开' : '标记解决' }}</el-button></template></el-table-column>
        </el-table>
        <div class="table-pagination"><span><Warning /> 共 {{ riskTotal }} 条记录</span><el-pagination v-model:current-page="riskPage" :page-size="20" layout="prev, pager, next" :total="riskTotal" @current-change="loadRisks" /></div>
      </el-tab-pane>
    </el-tabs>
  </AppLayout>
</template>
