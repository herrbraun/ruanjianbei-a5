<script setup lang="ts">
import { Delete, MagicStick, Plus, RefreshRight, Search, UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { knowledgeApi, type KnowledgeBase, type KnowledgeDocument, type RagProfile, type RagSearchPreviewResult, type ScenicArea } from '@/api/knowledge'
import AppLayout from '@/layouts/AppLayout.vue'

const areas = ref<ScenicArea[]>([])
const bases = ref<KnowledgeBase[]>([])
const profiles = ref<RagProfile[]>([])
const documents = ref<KnowledgeDocument[]>([])
const selectedAreaId = ref<number>()
const selectedProfileId = ref<number>()
const selectedBaseId = ref<number>()
const previewQuery = ref('九龙灌浴几点表演？')
const preview = ref<RagSearchPreviewResult>()
const file = ref<File>()
const fileInput = ref<HTMLInputElement>()
const loading = ref(false)
const uploading = ref(false)
const uploadPercent = ref(0)
const previewLoading = ref(false)
const pollingDocuments = ref(false)
const deletingDocumentId = ref<number>()
const showAreaDialog = ref(false)
const showBaseDialog = ref(false)
const showProfileDialog = ref(false)
const areaForm = ref({ code: '', name: '', description: '', is_enabled: true })
const baseForm = ref({ code: '', name: '', description: '', is_enabled: true })
const profileForm = ref({ name: '', status: 'draft' as 'draft' | 'active', top_k: 5, baseIds: [] as number[] })

const selectedArea = computed(() => areas.value.find((area) => area.id === selectedAreaId.value))
const selectedProfile = computed(() => profiles.value.find((profile) => profile.id === selectedProfileId.value))
let documentPollTimer: ReturnType<typeof setInterval> | undefined
let documentRefreshInFlight = false
let documentRefreshQueued = false

function errorText(error: unknown, fallback: string) {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  return detail || fallback
}

async function refreshProfiles() {
  profiles.value = (await knowledgeApi.listProfiles(selectedAreaId.value)).data
  if (!profiles.value.some((item) => item.id === selectedProfileId.value)) {
    selectedProfileId.value = profiles.value.find((item) => item.status === 'active')?.id ?? profiles.value[0]?.id
  }
}

function stopDocumentPolling() {
  if (documentPollTimer) clearInterval(documentPollTimer)
  documentPollTimer = undefined
  pollingDocuments.value = false
}

function startDocumentPolling() {
  if (documentPollTimer) return
  pollingDocuments.value = true
  documentPollTimer = setInterval(() => void loadDocuments(false), 1000)
}

function syncDocumentPolling() {
  if (documents.value.some((document) => document.status === 'pending' || document.status === 'indexing')) {
    startDocumentPolling()
  } else {
    stopDocumentPolling()
  }
}

async function loadDocuments(showError: boolean) {
  if (documentRefreshInFlight) {
    documentRefreshQueued = true
    return
  }
  documentRefreshInFlight = true
  const requestedBaseId = selectedBaseId.value
  try {
    const response = await knowledgeApi.listDocuments(requestedBaseId)
    if (requestedBaseId === selectedBaseId.value) {
      documents.value = response.data
      syncDocumentPolling()
    }
  } catch (error) {
    if (showError) ElMessage.error(errorText(error, '刷新资料状态失败'))
  } finally {
    documentRefreshInFlight = false
    if (documentRefreshQueued) {
      documentRefreshQueued = false
      void loadDocuments(false)
    }
  }
}

async function refreshDocuments() {
  await loadDocuments(true)
}

async function changeKnowledgeBase() {
  stopDocumentPolling()
  await loadDocuments(true)
}

async function refresh() {
  loading.value = true
  try {
    const [areaResponse, baseResponse] = await Promise.all([knowledgeApi.listScenicAreas(), knowledgeApi.listKnowledgeBases()])
    areas.value = areaResponse.data
    bases.value = baseResponse.data
    selectedAreaId.value ??= areas.value[0]?.id
    selectedBaseId.value ??= bases.value[0]?.id
    await Promise.all([refreshProfiles(), loadDocuments(true)])
  } catch (error) {
    ElMessage.error(errorText(error, '加载知识库平台失败'))
  } finally {
    loading.value = false
  }
}

async function createArea() {
  try {
    await knowledgeApi.createScenicArea(areaForm.value)
    areaForm.value = { code: '', name: '', description: '', is_enabled: true }
    showAreaDialog.value = false
    ElMessage.success('景区已创建')
    await refresh()
  } catch (error) { ElMessage.error(errorText(error, '创建景区失败')) }
}

async function createBase() {
  try {
    await knowledgeApi.createKnowledgeBase(baseForm.value)
    baseForm.value = { code: '', name: '', description: '', is_enabled: true }
    showBaseDialog.value = false
    ElMessage.success('知识库已创建')
    await refresh()
  } catch (error) { ElMessage.error(errorText(error, '创建知识库失败')) }
}

async function createProfile() {
  if (!selectedAreaId.value || !profileForm.value.baseIds.length) {
    ElMessage.warning('请选择景区并至少绑定一个知识库')
    return
  }
  try {
    await knowledgeApi.createProfile({
      scenic_area_id: selectedAreaId.value,
      name: profileForm.value.name,
      status: profileForm.value.status,
      top_k: profileForm.value.top_k,
      knowledge_bases: profileForm.value.baseIds.map((knowledgeBaseId) => ({
        knowledge_base_id: knowledgeBaseId,
        is_enabled: true,
        retrieval_priority: bases.value.find((base) => base.id === knowledgeBaseId)?.code.includes('structured') ? 100 : 10,
      })),
    })
    profileForm.value = { name: '', status: 'draft', top_k: 5, baseIds: [] }
    showProfileDialog.value = false
    ElMessage.success('RAG Profile 已创建')
    await refreshProfiles()
  } catch (error) { ElMessage.error(errorText(error, '创建 RAG Profile 失败')) }
}

async function activate(profile: RagProfile) {
  try {
    await ElMessageBox.confirm(`将“${profile.name}”设为 ${selectedArea.value?.name || '当前景区'} 的正式 Profile？旧正式版会自动归档。`, '切换正式 Profile', { type: 'warning' })
    await knowledgeApi.activateProfile(profile.id)
    ElMessage.success('正式 Profile 已切换')
    await refreshProfiles()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(errorText(error, '切换失败'))
  }
}

function selectFile(event: Event) {
  file.value = (event.target as HTMLInputElement).files?.[0]
}

async function upload() {
  if (!selectedBaseId.value || !file.value) { ElMessage.warning('请选择目标知识库和资料文件'); return }
  const form = new FormData()
  form.append('knowledge_base_id', String(selectedBaseId.value))
  form.append('file', file.value)
  uploading.value = true
  uploadPercent.value = 0
  try {
    const response = await knowledgeApi.uploadDocument(form, (event) => {
      if (event.total) uploadPercent.value = Math.round((event.loaded / event.total) * 100)
    })
    documents.value = [response.data, ...documents.value.filter((item) => item.id !== response.data.id)]
    file.value = undefined
    if (fileInput.value) fileInput.value.value = ''
    ElMessage.success('资料已接收，正在后台解析、切块和生成向量')
    startDocumentPolling()
    await loadDocuments(false)
  } catch (error) { ElMessage.error(errorText(error, '上传失败')) } finally {
    uploading.value = false
    uploadPercent.value = 0
  }
}

async function reindex(document: KnowledgeDocument) {
  try {
    const response = await knowledgeApi.reindexDocument(document.id)
    documents.value = documents.value.map((item) => item.id === document.id ? response.data : item)
    ElMessage.success('已提交重新索引任务，状态将每秒自动更新')
    startDocumentPolling()
  } catch (error) { ElMessage.error(errorText(error, '重新索引失败')) }
}

async function removeDocument(document: KnowledgeDocument) {
  try {
    await ElMessageBox.confirm(
      `确定删除“${document.original_filename}”吗？对应的切片、向量和本地原文件会一并删除，此操作无法撤销。`,
      '删除知识库资料',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' },
    )
    deletingDocumentId.value = document.id
    await knowledgeApi.deleteDocument(document.id)
    documents.value = documents.value.filter((item) => item.id !== document.id)
    syncDocumentPolling()
    ElMessage.success('资料、切片和向量已删除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(errorText(error, '删除资料失败'))
  } finally {
    deletingDocumentId.value = undefined
  }
}

function documentProgress(document: KnowledgeDocument) {
  if (document.status === 'indexed') return 100
  if (document.status === 'pending') return 5
  if (document.status === 'failed') {
    return document.chunk_count ? Math.min(95, Math.round((document.embedding_count / document.chunk_count) * 100)) : 0
  }
  if (!document.chunk_count) return 18
  return Math.min(95, 30 + Math.round((document.embedding_count / document.chunk_count) * 65))
}

function statusLabel(status: KnowledgeDocument['status']) {
  return { pending: '等待中', indexing: '处理中', indexed: '已完成', failed: '失败' }[status]
}

async function searchPreview() {
  if (!selectedAreaId.value || !selectedProfileId.value || !previewQuery.value.trim()) { ElMessage.warning('请选择景区、Profile 并输入问题'); return }
  previewLoading.value = true
  preview.value = undefined
  try {
    preview.value = (await knowledgeApi.previewSearch({ scenic_area_id: selectedAreaId.value, rag_profile_id: selectedProfileId.value, query: previewQuery.value })).data
  } catch (error) { ElMessage.error(errorText(error, '检索预览失败')) } finally { previewLoading.value = false }
}

onMounted(() => void refresh())
onBeforeUnmount(stopDocumentPolling)
</script>

<template>
  <AppLayout title="知识库" description="维护景区资料、检索范围和问答配置。" role-label="运营管理">
    <div v-loading="loading" class="knowledge-page">
      <section class="workspace-panel knowledge-toolbar">
        <div><p class="eyebrow">景区知识配置</p><h2>{{ selectedArea?.name || '选择景区' }}</h2><p>设置游客问答使用的知识范围，并在启用前进行检索验证。</p></div>
        <div class="toolbar-actions"><el-button :icon="Plus" @click="showAreaDialog = true">新建景区</el-button><el-button :icon="Plus" @click="showBaseDialog = true">新建知识库</el-button><el-button type="primary" :icon="Plus" @click="showProfileDialog = true">新建 Profile</el-button></div>
      </section>

      <section class="knowledge-control-grid">
        <article class="workspace-panel selector-panel"><span>1 · 景区</span><el-select v-model="selectedAreaId" placeholder="选择景区" @change="refreshProfiles"><el-option v-for="area in areas" :key="area.id" :label="area.name" :value="area.id" /></el-select><small>{{ selectedArea?.code }} · {{ selectedArea?.is_enabled ? '已启用' : '已停用' }}</small></article>
        <article class="workspace-panel selector-panel"><span>2 · RAG Profile</span><el-select v-model="selectedProfileId" placeholder="选择 Profile"><el-option v-for="profile in profiles" :key="profile.id" :label="`${profile.name} (${profile.status})`" :value="profile.id" /></el-select><small>{{ selectedProfile?.embedding_model || 'text-embedding-v4' }} · {{ selectedProfile?.embedding_dimensions || 1024 }} 维</small></article>
        <article class="workspace-panel selector-panel"><span>3 · 上传目标知识库</span><el-select v-model="selectedBaseId" placeholder="选择知识库" @change="changeKnowledgeBase"><el-option v-for="base in bases" :key="base.id" :label="base.name" :value="base.id" /></el-select><small>选择资料的归属位置</small></article>
      </section>

      <section class="profile-section"><div class="section-heading"><div><p class="eyebrow">PROFILE STATUS</p><h2>景区 RAG Profile</h2></div></div><div class="profile-grid"><article v-for="profile in profiles" :key="profile.id" class="profile-card" :class="{ active: profile.status === 'active' }"><div class="profile-card-head"><el-tag :type="profile.status === 'active' ? 'success' : profile.status === 'draft' ? 'warning' : 'info'">{{ profile.status }}</el-tag><strong class="profile-reference-count">每次最多参考 {{ profile.top_k }} 段资料</strong></div><h3>{{ profile.name }}</h3><p>{{ profile.knowledge_base_bindings.filter((binding) => binding.is_enabled).map((binding) => binding.knowledge_base?.name).join(' · ') || '尚未绑定知识库' }}</p><small class="profile-explanation">游客提问时，系统会先从这些知识库中选出最相关的 {{ profile.top_k }} 段内容作为回答依据。</small><el-button v-if="profile.status !== 'active'" size="small" type="primary" plain @click="activate(profile)">设为正式版</el-button></article></div></section>

      <section class="knowledge-two-column">
        <article class="workspace-panel upload-panel">
          <div class="section-heading">
            <div><p class="eyebrow">INGEST</p><h2>资料上传与索引</h2></div>
            <div class="ingest-actions">
              <span v-if="pollingDocuments" class="live-poll-indicator"><i />每 1 秒更新</span>
              <el-button :icon="RefreshRight" text @click="refreshDocuments">刷新</el-button>
            </div>
          </div>
          <p>支持 DOCX、TXT、可提取文字的 PDF；扫描 PDF 会提示先 OCR。单文件最大 20 MB。</p>
          <div class="upload-row">
            <input ref="fileInput" accept=".docx,.txt,.pdf" type="file" @change="selectFile" />
            <el-button type="primary" :icon="UploadFilled" :loading="uploading" @click="upload">{{ uploading ? `上传中 ${uploadPercent}%` : '开始索引' }}</el-button>
          </div>
          <el-progress v-if="uploading" :percentage="uploadPercent" :stroke-width="5" :show-text="false" class="upload-progress" />
          <el-table :data="documents" size="small" max-height="360" empty-text="当前知识库还没有资料">
            <el-table-column prop="original_filename" label="资料" min-width="155" show-overflow-tooltip />
            <el-table-column label="状态" width="92">
              <template #default="{ row }"><span class="document-status" :class="`is-${row.status}`"><i />{{ statusLabel(row.status) }}</span></template>
            </el-table-column>
            <el-table-column label="处理进度" min-width="155">
              <template #default="{ row }">
                <div class="document-progress"><el-progress :percentage="documentProgress(row)" :stroke-width="5" :show-text="false" /><small>{{ row.chunk_count }} 个切片 · {{ row.embedding_count }} 个向量</small></div>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="142" fixed="right">
              <template #default="{ row }">
                <el-button size="small" text :disabled="row.status === 'pending' || row.status === 'indexing'" @click="reindex(row)">重建</el-button>
                <el-button size="small" text type="danger" :icon="Delete" :loading="deletingDocumentId === row.id" :disabled="row.status === 'pending' || row.status === 'indexing'" @click="removeDocument(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <p v-for="document in documents.filter((item) => item.error_message)" :key="document.id" class="error-text">{{ document.original_filename }}：{{ document.error_message }}</p>
        </article>

        <article class="workspace-panel preview-panel-rag">
          <div class="section-heading"><div><p class="eyebrow">RETRIEVAL + GENERATION</p><h2>草稿 / 正式版回答预览</h2></div></div>
          <el-input v-model="previewQuery" type="textarea" :rows="3" maxlength="2000" show-word-limit placeholder="输入要验证的导览问题" @keyup.ctrl.enter="searchPreview" />
          <el-button type="primary" :icon="Search" class="preview-button" :loading="previewLoading" @click="searchPreview">检索并生成 AI 示例回答</el-button>
          <el-skeleton v-if="previewLoading" :rows="3" animated class="answer-skeleton" />
          <div v-if="preview" class="preview-result">
            <article class="ai-answer-card" :class="{ 'is-failed': preview.answer_status === 'failed' }">
              <div class="ai-answer-heading">
                <span class="ai-answer-icon"><el-icon><MagicStick /></el-icon></span>
                <div><small>真实模型回答示例</small><strong>{{ preview.answer_model || 'AI 回答服务' }}</strong></div>
                <span v-if="preview.answer_duration_ms" class="ai-latency">{{ (preview.answer_duration_ms / 1000).toFixed(1) }}s</span>
              </div>
              <p v-if="preview.ai_answer" class="ai-answer-content">{{ preview.ai_answer }}</p>
              <p v-else class="ai-answer-error">回答生成失败：{{ preview.answer_error || '模型服务暂时不可用' }}</p>
            </article>
            <p class="retrieval-summary">本次检索使用：{{ preview.knowledge_bases.join(' · ') }}，共返回 {{ preview.hits.length }} 段依据</p>
            <article v-for="(hit, index) in preview.hits" :key="hit.chunk_id" class="retrieval-hit">
              <div><span><el-tag size="small">资料 {{ index + 1 }}</el-tag><el-tag size="small" type="info">{{ hit.knowledge_base_name }}</el-tag></span><span>相似度 {{ hit.score.toFixed(3) }}</span></div>
              <strong>{{ hit.spot_name || hit.section || '资料片段' }}</strong>
              <p>{{ hit.content }}</p>
              <small>{{ hit.spot_id ? `景点 ID：${hit.spot_id} · ` : '' }}{{ hit.source_locator || '原始资料' }} · 优先级 {{ hit.source_priority }}</small>
            </article>
          </div>
        </article>
      </section>
    </div>

    <el-dialog v-model="showAreaDialog" title="新建景区" width="420px"><el-form label-position="top"><el-form-item label="景区编码"><el-input v-model="areaForm.code" placeholder="例如 lingshan-new" /></el-form-item><el-form-item label="景区名称"><el-input v-model="areaForm.name" /></el-form-item><el-form-item label="简介"><el-input v-model="areaForm.description" type="textarea" /></el-form-item></el-form><template #footer><el-button @click="showAreaDialog = false">取消</el-button><el-button type="primary" @click="createArea">创建</el-button></template></el-dialog>
    <el-dialog v-model="showBaseDialog" title="新建可复用知识库" width="420px"><el-form label-position="top"><el-form-item label="知识库编码"><el-input v-model="baseForm.code" placeholder="例如 lingshan-guide" /></el-form-item><el-form-item label="名称"><el-input v-model="baseForm.name" /></el-form-item><el-form-item label="说明"><el-input v-model="baseForm.description" type="textarea" /></el-form-item></el-form><template #footer><el-button @click="showBaseDialog = false">取消</el-button><el-button type="primary" @click="createBase">创建</el-button></template></el-dialog>
    <el-dialog v-model="showProfileDialog" title="新建 RAG Profile" width="500px"><el-form label-position="top"><el-form-item label="Profile 名称"><el-input v-model="profileForm.name" placeholder="例如 灵山春季活动草稿" /></el-form-item><el-form-item label="状态"><el-radio-group v-model="profileForm.status"><el-radio value="draft">草稿</el-radio><el-radio value="active">直接设为正式</el-radio></el-radio-group></el-form-item><el-form-item label="每次回答参考资料数"><div class="form-field-with-help"><el-input-number v-model="profileForm.top_k" :min="1" :max="20" /><small>系统会选取相应数量的相关资料辅助回答，一般保持 5 即可。</small></div></el-form-item><el-form-item label="绑定知识库"><el-checkbox-group v-model="profileForm.baseIds"><el-checkbox v-for="base in bases" :key="base.id" :value="base.id">{{ base.name }}</el-checkbox></el-checkbox-group></el-form-item></el-form><template #footer><el-button @click="showProfileDialog = false">取消</el-button><el-button type="primary" @click="createProfile">创建</el-button></template></el-dialog>
  </AppLayout>
</template>
