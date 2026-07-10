<script setup lang="ts">
import { Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

import { knowledgeApi, type RagSearchResult, type ScenicArea } from '@/api/knowledge'
import AppLayout from '@/layouts/AppLayout.vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const areas = ref<ScenicArea[]>([])
const selectedCode = ref('')
const query = ref('灵山大佛有什么文化意义？')
const result = ref<RagSearchResult>()
const searching = ref(false)
const selectedArea = computed(() => areas.value.find((area) => area.code === selectedCode.value))

async function loadAreas() {
  try {
    areas.value = (await knowledgeApi.listPublicScenicAreas()).data
    selectedCode.value = areas.value[0]?.code || ''
  } catch {
    ElMessage.error('景区列表加载失败')
  }
}

async function searchGuide() {
  if (!selectedCode.value || !query.value.trim()) {
    ElMessage.warning('请选择景区并输入问题')
    return
  }
  searching.value = true
  try {
    result.value = (await knowledgeApi.search({ scenic_area_code: selectedCode.value, query: query.value })).data
  } catch (error) {
    const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(detail || '暂时无法检索景区资料')
  } finally {
    searching.value = false
  }
}

onMounted(loadAreas)
</script>

<template>
  <AppLayout title="游客端" description="这里将承载数字人导游、景区问答、语音输入和个性化路线推荐。" role-label="当前身份：游客">
    <section class="workspace-grid">
      <article class="workspace-panel visitor-rag-panel">
        <p class="eyebrow">SCENIC GUIDE CONTEXT</p>
        <h2>选择景区，开始导览</h2>
        <p>当前导览上下文只检索所选景区的正式知识库，不会混入其他景区资料。</p>
        <el-select v-model="selectedCode" placeholder="选择景区" class="visitor-area-select">
          <el-option v-for="area in areas" :key="area.code" :label="area.name" :value="area.code" />
        </el-select>
        <small v-if="selectedArea">{{ selectedArea.description || `${selectedArea.name} 导览资料` }}</small>
        <el-input v-model="query" type="textarea" :rows="3" class="visitor-query" placeholder="例如：九龙灌浴几点表演？" />
        <el-button type="primary" :icon="Search" :loading="searching" @click="searchGuide">检索景区导览资料</el-button>
        <div v-if="result" class="visitor-hits">
          <p>使用 {{ result.rag_profile_name }} · {{ result.knowledge_bases.join('、') }}</p>
          <article v-for="hit in result.hits" :key="hit.chunk_id"><strong>{{ hit.spot_name || hit.section || hit.knowledge_base_name }}</strong><p>{{ hit.content }}</p><small>{{ hit.source_locator || hit.knowledge_base_name }} · 相似度 {{ hit.score.toFixed(3) }}</small></article>
        </div>
      </article>
      <article class="workspace-panel">
        <h2>智能问答</h2>
        <p>后续接入 RAG 知识库和大模型问答接口。</p>
        <p><strong>当前昵称：</strong>{{ authStore.user?.nickname }}</p>
      </article>

      <article class="workspace-panel">
        <h2>数字人播报</h2>
        <p>预留 2D 数字人展示区域，后续接入口型动画和 TTS 音频播放。</p>
      </article>

      <article class="workspace-panel">
        <h2>路线推荐</h2>
        <p>根据游客兴趣生成游览路线和讲解重点。</p>
        <p><strong>兴趣偏好：</strong>{{ authStore.user?.interest || '暂未填写' }}</p>
      </article>
    </section>
  </AppLayout>
</template>
