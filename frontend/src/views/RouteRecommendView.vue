<script setup lang="ts">
import { Check, Location, MapLocation, Timer } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { getInterestOptions } from '@/api/auth'
import { getSpots, type ScenicSpot } from '@/api/spots'
import { recommendRoute, submitRouteFeedback, type RoutePlan, type RoutePreference } from '@/api/routes'
import InterestSelector from '@/components/InterestSelector.vue'
import AppLayout from '@/layouts/AppLayout.vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const loading = ref(false)
const spotLoading = ref(false)
const feedbackLoading = ref(false)
const feedbackSubmitted = ref(false)
const routePlan = ref<RoutePlan | null>(null)
const spots = ref<ScenicSpot[]>([])
const interestOptions = ref<string[]>([])
const selectedInterests = ref<string[]>([...(authStore.user?.interests || [])])
const form = reactive({ duration_minutes: 120, start_spot_id: undefined as number | undefined, preference: 'balanced' as RoutePreference })
const feedback = reactive({ rating: 5, comment: '' })
const preferenceLabels: Record<RoutePreference, string> = { balanced: '综合平衡', priority: '核心景点优先', more_spots: '尽量多游览' }

async function loadSpots() {
  spotLoading.value = true
  try { spots.value = (await getSpots()).data }
  catch { ElMessage.error('起点列表加载失败，请刷新页面重试') }
  finally { spotLoading.value = false }
}

async function loadInterests() {
  try {
    interestOptions.value = (await getInterestOptions()).data.interests
    if (!selectedInterests.value.length && interestOptions.value.length) selectedInterests.value = [interestOptions.value[0]]
  } catch { ElMessage.error('兴趣标签加载失败，请刷新页面重试') }
}

async function createRoute() {
  loading.value = true
  feedbackSubmitted.value = false
  try {
    routePlan.value = (await recommendRoute({ interest: selectedInterests.value.join(','), duration_minutes: form.duration_minutes, start_spot_id: form.start_spot_id, preference: form.preference })).data
    ElMessage.success('路线已生成')
  } catch { ElMessage.error('路线生成失败，请检查起点或增加游玩时长') }
  finally { loading.value = false }
}

async function submitFeedback() {
  if (!routePlan.value) return
  feedbackLoading.value = true
  try {
    await submitRouteFeedback(routePlan.value.id, { rating: feedback.rating, comment: feedback.comment.trim() || undefined })
    feedbackSubmitted.value = true
    ElMessage.success('感谢你的反馈')
  } catch { ElMessage.error('反馈提交失败，请稍后重试') }
  finally { feedbackLoading.value = false }
}

onMounted(() => { loadSpots(); loadInterests() })
</script>

<template>
  <AppLayout title="路线推荐" description="选择兴趣、游玩时长和起点，规划本次行程。" role-label="游览服务">
    <template #actions><RouterLink to="/visitor/spots"><el-button>先浏览景点</el-button></RouterLink></template>

    <div class="route-workspace" :class="{ 'has-result': routePlan }">
      <section class="route-form-panel">
        <div class="section-heading compact"><div><span>路线条件</span><h2>告诉我们你的计划</h2></div></div>
        <el-form label-position="top" @submit.prevent="createRoute">
          <el-form-item label="兴趣偏好" required><div class="interest-field"><InterestSelector v-model="selectedInterests" :options="interestOptions" /><p class="selection-count">已选择 {{ selectedInterests.length }} / 8</p></div></el-form-item>
          <el-form-item label="游玩时长" required><div class="duration-control"><el-input-number v-model="form.duration_minutes" :min="15" :max="480" :step="15" /><span>分钟</span></div></el-form-item>
          <el-form-item label="起点（可选）"><el-select v-model="form.start_spot_id" filterable clearable :loading="spotLoading" placeholder="暂不指定起点"><el-option v-for="spot in spots" :key="spot.id" :label="`${spot.scenic_area} · ${spot.name}`" :value="spot.id" /></el-select></el-form-item>
          <el-form-item label="推荐偏好"><el-radio-group v-model="form.preference" class="preference-group"><el-radio-button value="balanced">综合平衡</el-radio-button><el-radio-button value="priority">核心优先</el-radio-button><el-radio-button value="more_spots">更多景点</el-radio-button></el-radio-group></el-form-item>
          <p class="form-helper">预计停留时间不会超过你设置的游玩时长。</p>
          <el-button class="full-button" type="primary" :icon="MapLocation" :loading="loading" :disabled="!selectedInterests.length" @click="createRoute">生成游览路线</el-button>
        </el-form>
      </section>

      <section v-if="routePlan" class="route-plan-panel" aria-live="polite">
        <header class="route-plan-header"><div><span>推荐路线 #{{ routePlan.id }}</span><h2>{{ preferenceLabels[routePlan.preference] }}</h2><p>{{ routePlan.reason }}</p></div><div class="route-duration"><el-icon><Timer /></el-icon><strong>{{ routePlan.total_duration_minutes }}</strong><span>/ {{ routePlan.duration_minutes }} 分钟</span></div></header>
        <ol class="route-timeline">
          <li v-for="spot in routePlan.spots" :key="spot.id"><div class="timeline-marker">{{ spot.sequence }}</div><article><div class="timeline-heading"><div><span v-if="spot.spot_id === routePlan.start_spot_id" class="start-label">起点</span><h3>{{ spot.name }}</h3></div><strong>{{ spot.stay_minutes }} 分钟</strong></div><p>{{ spot.summary }}</p><div class="route-location"><el-icon><Location /></el-icon><span>{{ spot.location || '位置待补充' }}</span></div><p class="route-basis">{{ spot.reason }}</p><RouterLink v-if="spot.spot_id" class="text-link" :to="`/visitor/spots/${spot.spot_id}`">查看景点详情</RouterLink></article></li>
        </ol>
        <section class="feedback-panel"><div><span>路线反馈</span><h3>{{ feedbackSubmitted ? '反馈已提交' : '这条路线适合你吗？' }}</h3></div><div v-if="feedbackSubmitted" class="feedback-success"><el-icon><Check /></el-icon><span>感谢你的评价，可再次提交以更新反馈。</span></div><el-rate v-model="feedback.rating" aria-label="路线评分" /><el-input v-model="feedback.comment" type="textarea" :rows="3" placeholder="补充你的游览感受（可选）" /><el-button type="primary" plain :loading="feedbackLoading" @click="submitFeedback">{{ feedbackSubmitted ? '更新反馈' : '提交反馈' }}</el-button></section>
      </section>

      <section v-else class="route-empty-state"><el-icon><MapLocation /></el-icon><h2>开始规划行程</h2><p>选择游览偏好和时长后，即可查看推荐路线。</p></section>
    </div>
  </AppLayout>
</template>
