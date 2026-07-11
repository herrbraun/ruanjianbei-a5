<script setup lang="ts">
import { ChatDotRound, Compass, Document, Loading, Microphone, Position, VideoPlay } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { guideApi, type GuideMessage, type GuideSource } from '@/api/guide'
import { knowledgeApi, type ScenicArea } from '@/api/knowledge'
import AppLayout from '@/layouts/AppLayout.vue'
import { useGuideStore } from '@/stores/guide'

const guideStore = useGuideStore()
const scenicAreas = ref<ScenicArea[]>([])
const selectedScenicCode = ref('')
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

let mediaRecorder: MediaRecorder | undefined
let mediaStream: MediaStream | undefined
let recordedChunks: BlobPart[] = []
let recordTimer: ReturnType<typeof setInterval> | undefined
let recordLimitTimer: ReturnType<typeof setTimeout> | undefined
let audio: HTMLAudioElement | undefined
let activeAudioUrl: string | undefined
let playbackGeneration = 0

const selectedScenicArea = computed(() => scenicAreas.value.find((area) => area.code === selectedScenicCode.value))
const messages = computed(() => guideStore.messages)
const sessionReady = computed(() => Boolean(guideStore.activeSession && !guideStore.loadingMessages))

function errorText(error: unknown, fallback: string) {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  return detail || fallback
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
    selectedScenicCode.value = scenicAreas.value[0]?.code || ''
  } catch (error) {
    ElMessage.error(errorText(error, '景区列表加载失败'))
  } finally {
    loadingAreas.value = false
  }
}

async function openGuideSession() {
  if (!selectedScenicCode.value) return
  try {
    stopAudio()
    await guideStore.openScenicArea(selectedScenicCode.value)
    await scrollToLatest()
  } catch (error) {
    ElMessage.error(errorText(error, '无法打开该景区的导览会话'))
  }
}

async function sendQuestion() {
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
  if (audio) {
    audio.pause()
  }
  if (activeAudioUrl) URL.revokeObjectURL(activeAudioUrl)
  audio = undefined
  activeAudioUrl = undefined
  playingMessageId.value = undefined
  speechLoadingMessageId.value = undefined
  activeAudioMessageId.value = undefined
}

async function playMessage(message: GuideMessage) {
  if (speechLoadingMessageId.value === message.id) {
    stopAudio()
    return
  }
  if (activeAudioMessageId.value === message.id && audio) {
    if (audio.paused) {
      try {
        await audio.play()
        playingMessageId.value = message.id
      } catch {
        ElMessage.info('音频已准备好，请点击播放讲解')
      }
      return
    }
    audio.pause()
    playingMessageId.value = undefined
    return
  }

  stopAudio()
  const generation = playbackGeneration
  speechLoadingMessageId.value = message.id
  try {
    const response = await guideApi.synthesize(message.id)
    if (generation !== playbackGeneration) return
    activeAudioUrl = URL.createObjectURL(response.data)
    audio = new Audio(activeAudioUrl)
    activeAudioMessageId.value = message.id
    playingMessageId.value = message.id
    speechLoadingMessageId.value = undefined
    audio.onended = () => {
      if (generation === playbackGeneration) stopAudio()
    }
    audio.onerror = () => {
      if (generation === playbackGeneration) stopAudio()
      ElMessage.error('音频播放失败，请重试')
    }
    try {
      await audio.play()
    } catch {
      playingMessageId.value = undefined
      ElMessage.info('音频已准备好，点击播放讲解即可收听')
    }
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

watch(selectedScenicCode, () => void openGuideSession())
watch(messages, () => void scrollToLatest(), { deep: true })

onMounted(() => void loadScenicAreas())
onBeforeUnmount(() => {
  stopRecordClock()
  if (mediaRecorder?.state === 'recording') mediaRecorder.stop()
  releaseMicrophone()
  stopAudio()
})
</script>

<template>
  <AppLayout title="智能导览会话" description="用文字或语音提问，随时获取景区讲解。" role-label="当前身份：游客">
    <section class="guide-page" v-loading="loadingAreas">
      <aside class="guide-context-card">
        <p class="eyebrow">SCENIC CONTEXT</p>
        <h2>从一座景区开始</h2>
        <el-select v-model="selectedScenicCode" class="guide-area-select" placeholder="选择景区" :disabled="loadingAreas">
          <el-option v-for="area in scenicAreas" :key="area.code" :label="area.name" :value="area.code" />
        </el-select>
        <div v-if="selectedScenicArea" class="guide-scenic-note">
          <Compass />
          <div>
            <strong>{{ selectedScenicArea.name }}</strong>
            <span>{{ selectedScenicArea.description || '已进入数字导览上下文' }}</span>
          </div>
        </div>
      </aside>

      <article class="guide-conversation-card">
        <header class="guide-conversation-heading">
          <div>
            <p class="eyebrow">ASK · LISTEN · EXPLORE</p>
            <h2>{{ selectedScenicArea?.name || '景区导览' }}</h2>
          </div>
          <span class="guide-session-status" :class="{ ready: sessionReady }">
            <i /> {{ sessionReady ? '导览已就绪' : '正在连接导览会话' }}
          </span>
        </header>

        <div ref="conversationElement" class="guide-message-stream">
          <div v-if="guideStore.loadingMessages" class="guide-empty-state"><el-icon class="is-loading"><Loading /></el-icon>正在恢复导览会话…</div>
          <div v-else-if="!messages.length" class="guide-empty-state guide-welcome-state">
            <span class="guide-welcome-icon"><ChatDotRound /></span>
            <strong>你好，我是你的景区导览助手。</strong>
            <p>试着问问“灵山大佛有什么文化意义？”或点击麦克风直接说出问题。</p>
          </div>

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
