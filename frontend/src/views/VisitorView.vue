<script setup lang="ts">
import { ArrowLeft, ArrowRight, Compass, Document, Loading, Microphone, Position, VideoPlay } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AvatarViewer from '@/components/AvatarViewer.vue'
import { avatarApi, avatarAssetUrl, type ScenicAvatar } from '@/api/avatar'
import { guideApi, guideSpeechStreamUrl, type GuideFeedbackTag, type GuideMessage, type GuideSource } from '@/api/guide'
import { knowledgeApi, type ScenicArea } from '@/api/knowledge'
import { getRoute } from '@/api/routes'
import AppLayout from '@/layouts/AppLayout.vue'
import { StreamingPcmPlayer } from '@/services/streamingPcmPlayer'
import { useAuthStore } from '@/stores/auth'
import { useGuideStore } from '@/stores/guide'
import { useScenicStore } from '@/stores/scenic'

const guideStore = useGuideStore()
const authStore = useAuthStore()
const scenicStore = useScenicStore()
const route = useRoute()
const router = useRouter()
const scenicAreas = ref<ScenicArea[]>([])
const selectedScenicCode = ref('')
const guideStarted = ref(false)
const draft = ref('')
const draftInputMode = ref<'text' | 'voice'>('text')
const loadingAreas = ref(false)
const transcribing = ref(false)
const recording = ref(false)
const recordingSeconds = ref(0)
const playingMessageId = ref<number>()
const speechLoadingMessageId = ref<number>()
const activeAudioMessageId = ref<number>()
const conversationElement = ref<HTMLElement>()
const scenicAvatars = ref<ScenicAvatar[]>([])
const selectedAvatarId = ref<number>()
const avatarListLoading = ref(false)
const avatarRenderError = ref('')
const audioLevel = ref(0)
const avatarGesture = ref<'welcome' | 'guiding'>()
const avatarWelcomeRequest = ref(0)
const routeActionLoading = ref(false)
const feedbackLoading = ref(false)
const feedbackSaving = ref(false)
const feedbackSubmitted = ref(false)
const feedbackForm = reactive({ rating: 5, tags: [] as GuideFeedbackTag[], comment: '' })
const feedbackTagOptions: Array<{ value: GuideFeedbackTag; label: string }> = [
  { value: 'answer_accurate', label: '回答准确' },
  { value: 'voice_natural', label: '语音自然' },
  { value: 'avatar_preferred', label: '形象喜欢' },
  { value: 'slow_response', label: '响应较慢' },
  { value: 'unresolved', label: '问题未解决' },
]

let mediaRecorder: MediaRecorder | undefined
let mediaStream: MediaStream | undefined
let recordedChunks: BlobPart[] = []
let recordTimer: ReturnType<typeof setInterval> | undefined
let recordLimitTimer: ReturnType<typeof setTimeout> | undefined
let playbackGeneration = 0
let avatarGestureTimer: ReturnType<typeof setTimeout> | undefined
const pcmPlayer = new StreamingPcmPlayer({
  onFirstAudio: () => {
    speechLoadingMessageId.value = undefined
    if (activeAudioMessageId.value) playingMessageId.value = activeAudioMessageId.value
    triggerAvatarGesture('guiding', 1_800)
  },
  onLevel: (level) => { audioLevel.value = level },
  onEnded: () => stopAudio(),
})

const selectedScenicArea = computed(() => scenicAreas.value.find((area) => area.code === selectedScenicCode.value))
const messages = computed(() => guideStore.messages)
const hasAssistantAnswer = computed(() => messages.value.some((message) => message.role === 'assistant' && message.status === 'success'))
const sessionReady = computed(() => guideStarted.value && Boolean(guideStore.activeSession && !guideStore.loadingMessages))
const activeAvatar = computed(() => scenicAvatars.value.find((avatar) => avatar.id === selectedAvatarId.value))
const activeRouteContext = computed(() => guideStore.activeRouteContext)
const currentRouteSpot = computed(() => activeRouteContext.value?.spots.find((spot) => spot.spot_id === activeRouteContext.value?.current_spot_id))
const currentRouteIndex = computed(() => activeRouteContext.value?.spots.findIndex((spot) => spot.spot_id === activeRouteContext.value?.current_spot_id) ?? -1)
const hasPreviousRouteSpot = computed(() => currentRouteIndex.value > 0)
const hasNextRouteSpot = computed(() => Boolean(activeRouteContext.value && currentRouteIndex.value >= 0 && currentRouteIndex.value < activeRouteContext.value.spots.length - 1))
const routeControlsBusy = computed(() => routeActionLoading.value || guideStore.sending || guideStore.updatingRouteContext)
const avatarAsset = computed(() => (
  selectedScenicCode.value && activeAvatar.value
    ? avatarAssetUrl(selectedScenicCode.value, activeAvatar.value.id)
    : null
))
const avatarMotion = computed<'idle' | 'listening' | 'thinking' | 'speaking' | 'welcome' | 'guiding'>(() => {
  if (recording.value) return 'listening'
  if (guideStore.sending) return 'thinking'
  if (avatarGesture.value) return avatarGesture.value
  if (speechLoadingMessageId.value) return 'thinking'
  if (playingMessageId.value) return 'speaking'
  return 'idle'
})

function errorText(error: unknown, fallback: string) {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  return detail || (error instanceof Error ? error.message : fallback)
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

function sourceTitle(source: GuideSource) {
  return source.spot_name || source.section || source.knowledge_base_name
}

function displayMessageContent(content: string) {
  return content.replace(/\s*\[(?:资料|来源|來源)\s*[0-9一二三四五六七八九十]+\]/g, '').trim()
}

async function scrollToLatest() {
  await nextTick()
  if (conversationElement.value) conversationElement.value.scrollTop = conversationElement.value.scrollHeight
}

async function loadScenicAreas() {
  loadingAreas.value = true
  try {
    scenicAreas.value = (await knowledgeApi.listPublicScenicAreas()).data
    const requestedCode = typeof route.query.scenic_code === 'string' ? route.query.scenic_code : scenicStore.selectedCode
    selectedScenicCode.value = scenicAreas.value.some((area) => area.code === requestedCode)
      ? requestedCode
      : scenicAreas.value[0]?.code || ''
    const selected = scenicAreas.value.find((area) => area.code === selectedScenicCode.value)
    if (selected) scenicStore.select(selected)
  } catch (error) {
    ElMessage.error(errorText(error, '景区列表加载失败'))
  } finally {
    loadingAreas.value = false
  }
}

function avatarStorageKey(scenicCode: string) {
  return `ai-tour-guide:avatar:${scenicCode}`
}

function clearAvatarGesture() {
  if (avatarGestureTimer) clearTimeout(avatarGestureTimer)
  avatarGestureTimer = undefined
  avatarGesture.value = undefined
}

function triggerAvatarGesture(gesture: 'welcome' | 'guiding', duration: number) {
  clearAvatarGesture()
  avatarGesture.value = gesture
  avatarGestureTimer = setTimeout(() => {
    avatarGesture.value = undefined
    avatarGestureTimer = undefined
  }, duration)
}

function requestAvatarWelcome() {
  avatarWelcomeRequest.value += 1
}

async function loadScenicAvatars() {
  const scenicCode = selectedScenicCode.value
  scenicAvatars.value = []
  selectedAvatarId.value = undefined
  avatarRenderError.value = ''
  if (!scenicCode) return
  avatarListLoading.value = true
  try {
    const { data } = await avatarApi.listPublicScenicAvatars(scenicCode)
    if (scenicCode !== selectedScenicCode.value) return
    scenicAvatars.value = data.avatars
    const storedId = Number(localStorage.getItem(avatarStorageKey(scenicCode)))
    const storedAvatarExists = data.avatars.some((avatar) => avatar.id === storedId)
    selectedAvatarId.value = storedAvatarExists
      ? storedId
      : data.default_variant_id || data.avatars[0]?.id
  } catch (error) {
    avatarRenderError.value = errorText(error, '数字人列表暂时不可用，仍可继续文字与语音讲解')
  } finally {
    avatarListLoading.value = false
  }
}

function onAvatarSelectionChange(avatarId: number | string) {
  const avatar = scenicAvatars.value.find((item) => item.id === Number(avatarId))
  if (!avatar) return
  stopAudio()
  avatarRenderError.value = ''
  localStorage.setItem(avatarStorageKey(selectedScenicCode.value), String(avatar.id))
  requestAvatarWelcome()
}

async function openGuideSession(routePlanId?: number, currentSpotId?: number) {
  if (!selectedScenicCode.value) return
  try {
    stopAudio()
    await guideStore.openScenicArea(selectedScenicCode.value, routePlanId, currentSpotId)
    await scrollToLatest()
  } catch (error) {
    ElMessage.error(errorText(error, '无法打开该景区的导览会话'))
  }
}

async function startGuide(routePlanId?: number, currentSpotId?: number) {
  if (!selectedScenicCode.value) {
    ElMessage.warning('请先选择景区')
    return
  }
  requestAvatarWelcome()
  const selected = scenicAreas.value.find((area) => area.code === selectedScenicCode.value)
  if (selected) scenicStore.select(selected)
  guideStarted.value = true
  await Promise.all([openGuideSession(routePlanId, currentSpotId), loadScenicAvatars()])
  if (!guideStore.activeSession) {
    guideStarted.value = false
    return
  }
}

async function sendRouteIntroduction(spotId?: number) {
  const context = activeRouteContext.value
  if (!context || routeControlsBusy.value) return
  const target = context.spots.find((spot) => spot.spot_id === (spotId || context.current_spot_id))
  if (!target) return
  routeActionLoading.value = true
  try {
    if (target.spot_id !== context.current_spot_id) await guideStore.setRouteStop(context.route_plan_id, target.spot_id)
    await router.replace({ path: route.path, query: { route_id: String(context.route_plan_id), spot_id: String(target.spot_id) } })
    triggerAvatarGesture('guiding', 2200)
    draft.value = `我们现在到达路线第 ${target.sequence} 站“${target.name}”。请结合我的兴趣“${context.interest}”主动讲解这一站，并简要告诉我它与后续行程的联系。`
    await sendQuestion()
  } catch (error) {
    ElMessage.error(errorText(error, '当前站讲解启动失败，请重试'))
  } finally {
    routeActionLoading.value = false
  }
}

async function moveRoute(step: number, introduce: boolean) {
  const context = activeRouteContext.value
  const nextIndex = currentRouteIndex.value + step
  const target = context?.spots[nextIndex]
  if (!context || !target || routeControlsBusy.value) return
  routeActionLoading.value = true
  try {
    await guideStore.setRouteStop(context.route_plan_id, target.spot_id)
    await router.replace({ path: route.path, query: { route_id: String(context.route_plan_id), spot_id: String(target.spot_id) } })
    triggerAvatarGesture('guiding', 1800)
    if (introduce) {
      draft.value = `我们现在到达路线第 ${target.sequence} 站“${target.name}”。请结合我的兴趣“${context.interest}”主动讲解这一站，并简要告诉我它与后续行程的联系。`
      await sendQuestion()
    } else ElMessage.success(`已切换到第 ${target.sequence} 站：${target.name}`)
  } catch (error) {
    ElMessage.error(errorText(error, '行程进度更新失败'))
  } finally {
    routeActionLoading.value = false
  }
}

async function initializeGuidePage() {
  await loadScenicAreas()
  const routePlanId = Number(route.query.route_id)
  const currentSpotId = Number(route.query.spot_id)
  if (!Number.isInteger(routePlanId) || !Number.isInteger(currentSpotId) || routePlanId <= 0 || currentSpotId <= 0) {
    if (typeof route.query.scenic_code === 'string' && scenicAreas.value.some((area) => area.code === route.query.scenic_code)) {
      await startGuide()
      if (guideStore.activeSession && route.query.start === '1') {
        await router.replace({ path: route.path, query: { scenic_code: selectedScenicCode.value } })
      }
    }
    return
  }
  try {
    const routePlan = (await getRoute(routePlanId)).data
    const scenicArea = scenicAreas.value.find((area) => area.name === routePlan.scenic_area)
    if (!scenicArea) throw new Error('Route scenic area is unavailable')
    selectedScenicCode.value = scenicArea.code
    await startGuide(routePlanId, currentSpotId)
    if (guideStore.activeSession && route.query.start === '1') {
      await router.replace({ path: route.path, query: { route_id: String(routePlanId), spot_id: String(currentSpotId) } })
      await sendRouteIntroduction(currentSpotId)
    }
  } catch (error) {
    ElMessage.error(errorText(error, '无法从这条路线开始数字人导览'))
  }
}

async function returnToScenicSelection() {
  if (routeControlsBusy.value || guideStore.loadingMessages) return
  stopAudio()
  clearAvatarGesture()
  routeActionLoading.value = false
  guideStore.closeActiveGuide()
  scenicStore.clear()
  guideStarted.value = false
  await router.push('/')
}

async function sendQuestion() {
  if (guideStore.sending) return
  const content = draft.value.trim()
  if (!content) {
    ElMessage.warning('请输入问题，或点击麦克风录音')
    return
  }
  if (!guideStore.activeSession) {
    await openGuideSession()
    if (!guideStore.activeSession) return
  }
  const inputMode = draftInputMode.value
  draft.value = ''
  draftInputMode.value = 'text'
  try {
    const response = await guideStore.send(content, inputMode)
    if (response.assistant_message.status === 'failed') ElMessage.warning('导览回答暂时不可用，请稍后再试')
    await scrollToLatest()
    if (response.assistant_message.status === 'success') void playMessage(response.assistant_message)
  } catch (error) {
    draft.value = content
    draftInputMode.value = inputMode
    ElMessage.error(errorText(error, '导览回答失败，请稍后再试'))
  }
}

function stopRecordClock() {
  if (recordTimer) clearInterval(recordTimer)
  if (recordLimitTimer) clearTimeout(recordLimitTimer)
  recordTimer = undefined
  recordLimitTimer = undefined
}

function releaseMicrophone() {
  mediaStream?.getTracks().forEach((track) => track.stop())
  mediaStream = undefined
}

async function startRecording() {
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    ElMessage.error('当前浏览器不支持录音，请使用文本提问')
    return
  }
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const preferredMime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : undefined
    mediaRecorder = new MediaRecorder(mediaStream, preferredMime ? { mimeType: preferredMime } : undefined)
    recordedChunks = []
    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size) recordedChunks.push(event.data)
    }
    mediaRecorder.onstop = () => void transcribeRecording()
    mediaRecorder.start()
    recording.value = true
    recordingSeconds.value = 0
    recordTimer = setInterval(() => { recordingSeconds.value += 1 }, 1000)
    recordLimitTimer = setTimeout(() => {
      ElMessage.warning('单次录音最长 90 秒，已自动结束')
      stopRecording()
    }, 90_000)
  } catch {
    releaseMicrophone()
    ElMessage.error('无法使用麦克风，请检查浏览器授权')
  }
}

function stopRecording() {
  stopRecordClock()
  recording.value = false
  if (mediaRecorder?.state === 'recording') mediaRecorder.stop()
  else releaseMicrophone()
}

async function transcribeRecording() {
  releaseMicrophone()
  const blob = new Blob(recordedChunks, { type: mediaRecorder?.mimeType || 'audio/webm' })
  mediaRecorder = undefined
  if (!blob.size) {
    ElMessage.warning('没有收到有效录音，请重试')
    return
  }
  transcribing.value = true
  try {
    const result = await guideApi.transcribe(blob)
    draft.value = result.data.transcript
    draftInputMode.value = 'voice'
    ElMessage.success('语音已识别，可确认文字后发送')
  } catch (error) {
    ElMessage.error(errorText(error, '语音识别失败，请重试'))
  } finally {
    transcribing.value = false
  }
}

function stopAudio() {
  playbackGeneration += 1
  pcmPlayer.stop()
  playingMessageId.value = undefined
  speechLoadingMessageId.value = undefined
  activeAudioMessageId.value = undefined
  audioLevel.value = 0
  clearAvatarGesture()
}

async function playMessage(message: GuideMessage) {
  if (speechLoadingMessageId.value === message.id) {
    stopAudio()
    return
  }
  if (activeAudioMessageId.value === message.id) {
    if (pcmPlayer.isPaused) {
      try {
        await pcmPlayer.resume()
        playingMessageId.value = message.id
      } catch {
        ElMessage.info('音频已准备好，请点击播放讲解')
      }
      return
    }
    await pcmPlayer.pause()
    playingMessageId.value = undefined
    return
  }

  stopAudio()
  const generation = playbackGeneration
  speechLoadingMessageId.value = message.id
  activeAudioMessageId.value = message.id
  try {
    const token = authStore.token || await authStore.recoverGuestSession()
    await pcmPlayer.play(
      guideSpeechStreamUrl(message.id, selectedAvatarId.value),
      token,
      () => authStore.recoverGuestSession(),
    )
  } catch (error) {
    if (generation !== playbackGeneration) return
    stopAudio()
    ElMessage.error(errorText(error, '语音合成失败，请稍后再试'))
  }
}

function speechButtonText(message: GuideMessage) {
  if (speechLoadingMessageId.value === message.id) return '取消播报'
  if (playingMessageId.value === message.id) return '暂停讲解'
  if (activeAudioMessageId.value === message.id) return '继续讲解'
  return '播放讲解'
}

function onAvatarRenderError(message: string) {
  avatarRenderError.value = `${message}，已切换为静态展示，不影响文字与语音讲解。`
}

function resetFeedback() {
  feedbackForm.rating = 5
  feedbackForm.tags = []
  feedbackForm.comment = ''
  feedbackSubmitted.value = false
}

async function loadFeedback() {
  const sessionId = guideStore.activeSession?.id
  resetFeedback()
  if (!sessionId) return
  feedbackLoading.value = true
  try {
    const { data } = await guideApi.getFeedback(sessionId)
    if (data && typeof data === 'object') {
      feedbackForm.rating = data.rating
      feedbackForm.tags = [...data.tags]
      feedbackForm.comment = data.comment || ''
      feedbackSubmitted.value = true
    }
  } catch (error) {
    ElMessage.error(errorText(error, '体验评价加载失败'))
  } finally {
    feedbackLoading.value = false
  }
}

async function saveFeedback() {
  const sessionId = guideStore.activeSession?.id
  if (!sessionId) return
  feedbackSaving.value = true
  try {
    await guideApi.saveFeedback(sessionId, {
      rating: feedbackForm.rating,
      tags: feedbackForm.tags,
      comment: feedbackForm.comment.trim() || undefined,
    })
    feedbackSubmitted.value = true
    ElMessage.success('感谢反馈，我们会继续改进导览体验')
  } catch (error) {
    ElMessage.error(errorText(error, '体验评价保存失败'))
  } finally {
    feedbackSaving.value = false
  }
}

watch(messages, () => void scrollToLatest(), { deep: true })
watch(() => guideStore.activeSession?.id, () => void loadFeedback())

onMounted(() => void initializeGuidePage())
onBeforeUnmount(() => {
  stopRecordClock()
  if (mediaRecorder?.state === 'recording') mediaRecorder.stop()
  releaseMicrophone()
  stopAudio()
  void pcmPlayer.destroy()
  clearAvatarGesture()
})
</script>

<template>
  <AppLayout title="智能导览" description="选择景区，与数字讲解员开始对话。" role-label="游览服务">
    <section class="guide-page" v-loading="loadingAreas">
      <article v-if="!guideStarted" class="guide-launch-card">
        <p class="eyebrow">选择景区</p>
        <h2>先选一座景区</h2>
        <p>从景区文化、路线安排到演出时间，让讲解员陪你慢慢逛。</p>
        <el-select v-model="selectedScenicCode" class="guide-area-select" placeholder="请选择景区" :disabled="loadingAreas">
          <el-option v-for="area in scenicAreas" :key="area.code" :label="area.name" :value="area.code" />
        </el-select>
        <div v-if="selectedScenicArea" class="guide-scenic-note">
          <Compass />
          <div>
            <strong>{{ selectedScenicArea.name }}</strong>
            <span>{{ selectedScenicArea.description || '已进入数字导览上下文' }}</span>
          </div>
        </div>
        <el-button class="guide-start-button" type="primary" size="large" :disabled="!selectedScenicCode || loadingAreas" @click="startGuide">
          开始导览 <Compass />
        </el-button>
      </article>

      <article v-else class="guide-conversation-card" :class="{ 'has-route-context': activeRouteContext }">
        <header class="guide-conversation-heading">
          <div>
            <p class="eyebrow">ASK · LISTEN · EXPLORE</p>
            <h2>{{ selectedScenicArea?.name || '景区导览' }}</h2>
          </div>
          <div class="guide-conversation-tools">
            <el-button text :disabled="routeControlsBusy || guideStore.loadingMessages" @click="returnToScenicSelection">切换景区</el-button>
            <span class="guide-session-status" :class="{ ready: sessionReady }"><i />{{ sessionReady ? '导览已就绪' : '正在连接' }}</span>
          </div>
        </header>

        <section v-if="activeRouteContext && currentRouteSpot" class="guide-route-progress" aria-label="当前个性化行程">
          <div class="guide-route-progress-main">
            <span>个性化行程 · {{ activeRouteContext.interest }}</span>
            <strong>第 {{ currentRouteSpot.sequence }} / {{ activeRouteContext.total_spots }} 站 · {{ currentRouteSpot.name }}</strong>
            <p>{{ currentRouteSpot.reason }}</p>
          </div>
          <div class="guide-route-actions">
            <el-button size="small" :icon="ArrowLeft" :disabled="!hasPreviousRouteSpot || routeControlsBusy" @click="moveRoute(-1, false)">上一站</el-button>
            <el-button size="small" plain :disabled="routeControlsBusy" @click="sendRouteIntroduction()">讲解当前站</el-button>
            <el-button size="small" :icon="ArrowRight" :disabled="!hasNextRouteSpot || routeControlsBusy" @click="moveRoute(1, false)">下一站</el-button>
            <el-button size="small" type="primary" :disabled="!hasNextRouteSpot || routeControlsBusy" @click="moveRoute(1, true)">继续导览</el-button>
          </div>
          <div class="guide-route-dots" aria-hidden="true"><i v-for="spot in activeRouteContext.spots" :key="spot.spot_id" :class="{ active: spot.spot_id === activeRouteContext.current_spot_id, passed: spot.sequence < currentRouteSpot.sequence }" /></div>
        </section>

        <div ref="conversationElement" class="guide-message-stream">
          <section class="guide-assistant-intro" :aria-busy="avatarListLoading">
            <div class="guide-assistant-intro-top">
              <div class="guide-avatar-picker" v-if="scenicAvatars.length">
                <label for="visitor-avatar-select">选择讲解员</label>
                <el-select id="visitor-avatar-select" v-model="selectedAvatarId" placeholder="选择人物" @change="onAvatarSelectionChange">
                  <el-option v-for="avatar in scenicAvatars" :key="avatar.id" :label="`${avatar.name} · ${avatar.outfit_name}`" :value="avatar.id" />
                </el-select>
              </div>
              <span v-else-if="!avatarListLoading" class="guide-avatar-empty">当前可使用文字与语音导览。</span>
            </div>
            <div class="guide-assistant-presence">
              <div class="guide-avatar-canvas guide-assistant-avatar" :class="`is-${avatarMotion}`">
                <AvatarViewer :asset-url="avatarAsset" :state="avatarMotion" :audio-level="audioLevel" :welcome-request="avatarWelcomeRequest" @error="onAvatarRenderError">
                  <div class="guide-avatar-fallback">
                    <span>{{ activeAvatar?.name?.slice(-1) || '灵' }}</span>
                    <strong>{{ activeAvatar?.name || '数字讲解员' }}</strong>
                    <small>文字与语音导览始终可用</small>
                  </div>
                </AvatarViewer>
                <span class="guide-avatar-state"><i />{{ avatarMotion === 'speaking' ? '正在讲解' : avatarMotion === 'thinking' ? '正在思考' : avatarMotion === 'guiding' ? '正在指引' : avatarMotion === 'welcome' ? '正在问候' : avatarMotion === 'listening' ? '正在聆听' : '随时为您服务' }}</span>
              </div>
              <div class="guide-welcome-bubble">
                <span>{{ activeAvatar?.name || '景区讲解员' }}</span>
                <strong>{{ currentRouteSpot ? `路线第 ${currentRouteSpot.sequence} 站：${currentRouteSpot.name}` : `欢迎来到${selectedScenicArea?.name || '景区'}！` }}</strong>
                <p>{{ currentRouteSpot ? `我会按“${activeRouteContext?.interest}”偏好调整讲解重点，并陪你走完这条路线。` : '我是你的数字讲解员。想了解景点故事、游览路线，还是今天的演出安排？' }}</p>
              </div>
            </div>
            <p v-if="avatarRenderError" class="guide-avatar-error">{{ avatarRenderError }}</p>
          </section>

          <div v-if="guideStore.loadingMessages" class="guide-empty-state"><el-icon class="is-loading"><Loading /></el-icon>正在恢复导览会话…</div>
          <p v-else-if="!messages.length" class="guide-question-nudge">试着问问“这里有哪些必看的景点？”也可以按下麦克风直接说出来。</p>

          <article v-for="message in messages" :key="message.id" class="guide-message" :class="`is-${message.role}`">
            <div class="guide-message-avatar">{{ message.role === 'user' ? '游' : '导' }}</div>
            <div class="guide-message-body">
              <div class="guide-message-meta">
                <strong>{{ message.role === 'user' ? '游客提问' : '智能讲解' }}</strong>
                <span v-if="message.input_mode === 'voice'">语音识别</span>
                <time>{{ formatTime(message.created_at) }}</time>
              </div>
              <div class="guide-message-content" :class="{ failed: message.status === 'failed' }">{{ displayMessageContent(message.content) }}</div>

              <template v-if="message.role === 'assistant' && message.status === 'success'">
                <div class="guide-answer-actions">
                  <el-button size="small" type="primary" plain :icon="VideoPlay" :loading="speechLoadingMessageId === message.id" @click="playMessage(message)">
                    {{ speechButtonText(message) }}
                  </el-button>
                </div>
                <details v-if="message.sources?.length" class="guide-sources">
                  <summary><Document /> 查看更多相关资料</summary>
                  <div class="guide-source-list">
                    <article v-for="source in message.sources" :key="source.chunk_id" class="guide-source-card">
                      <div><strong>{{ sourceTitle(source) }}</strong></div>
                      <p>{{ source.content }}</p>
                    </article>
                  </div>
                </details>
              </template>
            </div>
          </article>
        </div>

        <details v-if="hasAssistantAnswer" class="guide-feedback-card">
          <summary>{{ feedbackSubmitted ? '已提交体验评价' : '本次导览体验如何？' }}</summary>
          <div v-loading="feedbackLoading" class="guide-feedback-form">
            <div class="guide-feedback-rating">
              <span>整体满意度</span>
              <el-rate v-model="feedbackForm.rating" show-text :texts="['很不满意', '不满意', '一般', '满意', '非常满意']" />
            </div>
            <el-checkbox-group v-model="feedbackForm.tags" class="guide-feedback-tags">
              <el-checkbox-button v-for="option in feedbackTagOptions" :key="option.value" :value="option.value">{{ option.label }}</el-checkbox-button>
            </el-checkbox-group>
            <el-input v-model="feedbackForm.comment" type="textarea" :rows="2" maxlength="1000" show-word-limit placeholder="还可以告诉我们哪里做得好，或哪里需要改进（选填）" />
            <el-button type="primary" :loading="feedbackSaving" @click="saveFeedback">{{ feedbackSubmitted ? '更新评价' : '提交评价' }}</el-button>
          </div>
        </details>

        <footer class="guide-composer">
          <div class="guide-composer-mode" :class="{ voice: draftInputMode === 'voice' }">
            <Microphone v-if="draftInputMode === 'voice'" />
            <span>{{ draftInputMode === 'voice' ? '来自语音识别，可编辑后发送' : '文字提问' }}</span>
          </div>
          <el-input v-model="draft" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" :disabled="!sessionReady || guideStore.sending" placeholder="例如：九龙灌浴几点表演？" @keydown.enter.exact.prevent="sendQuestion" />
          <div class="guide-composer-actions">
            <el-button class="guide-record-button" :class="{ recording }" :loading="transcribing" :disabled="!sessionReady || guideStore.sending || transcribing" @click="recording ? stopRecording() : startRecording()">
              <Microphone />
              {{ transcribing ? '正在识别…' : recording ? `结束说话 ${recordingSeconds}s` : '开始说话' }}
            </el-button>
            <el-button type="primary" :icon="Position" :loading="guideStore.sending" :disabled="!sessionReady || transcribing" @click="sendQuestion">发送提问</el-button>
          </div>
        </footer>
      </article>
    </section>
  </AppLayout>
</template>
