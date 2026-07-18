<script setup lang="ts">
import { Delete, MagicStick, Plus, RefreshRight, Search, UploadFilled } from '@element-plus/icons-vue'
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
    ElMessage.error(errorText(error, '问答资料加载失败'))
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
    ElMessage.success('资料分组已创建')
    await refresh()
  } catch (error) { ElMessage.error(errorText(error, '创建资料分组失败')) }
}

async function createProfile() {
  if (!selectedAreaId.value || !profileForm.value.baseIds.length) {
    ElMessage.warning('请选择景区并至少关联一个资料分组')
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
    ElMessage.success('问答方案已创建')
    await refreshProfiles()
  } catch (error) { ElMessage.error(errorText(error, '创建问答方案失败')) }
}

async function activate(profile: RagProfile) {
  try {
    await ElMessageBox.confirm(`将“${profile.name}”设为 ${selectedArea.value?.name || '当前景区'} 当前使用的问答方案？原方案会自动归档。`, '启用问答方案', { type: 'warning' })
    await knowledgeApi.activateProfile(profile.id)
    ElMessage.success('问答方案已启用')
    await refreshProfiles()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(errorText(error, '切换失败'))
  }
}

function selectFile(event: Event) {
  file.value = (event.target as HTMLInputElement).files?.[0]
}

async function upload() {
  if (!selectedBaseId.value || !file.value) { ElMessage.warning('请选择资料分组和要上传的文件'); return }
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
    ElMessage.success('资料已上传，正在整理内容')
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
    ElMessage.success('资料已重新提交整理')
    startDocumentPolling()
  } catch (error) { ElMessage.error(errorText(error, '重新整理资料失败')) }
}

async function removeDocument(document: KnowledgeDocument) {
  try {
    await ElMessageBox.confirm(
      `确定删除“${document.original_filename}”吗？删除后讲解员将不再参考这份资料，此操作无法撤销。`,
      '删除问答资料',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' },
    )
    deletingDocumentId.value = document.id
    await knowledgeApi.deleteDocument(document.id)
    documents.value = documents.value.filter((item) => item.id !== document.id)
    syncDocumentPolling()
    ElMessage.success('资料已删除')
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
  if (!selectedAreaId.value || !selectedProfileId.value || !previewQuery.value.trim()) { ElMessage.warning('请选择景区、问答方案并输入问题'); return }
  previewLoading.value = true
  preview.value = undefined
  try {
    preview.value = (await knowledgeApi.previewSearch({ scenic_area_id: selectedAreaId.value, rag_profile_id: selectedProfileId.value, query: previewQuery.value })).data
  } catch (error) { ElMessage.error(errorText(error, '暂时无法查看回答效果')) } finally { previewLoading.value = false }
}

onMounted(() => void refresh())
onBeforeUnmount(stopDocumentPolling)
</script>

<template>
  <AppLayout title="问答资料" description="维护讲解员回答游客问题时参考的景区资料。" role-label="景区运营">
    <div v-loading="loading" class="knowledge-page">
      <section class="workspace-panel knowledge-toolbar">
        <div><p class="eyebrow">讲解问答</p><h2>{{ selectedArea?.name || '选择景区' }}</h2><p>设置讲解员可以参考的资料，并在发布前检查回答效果。</p></div>
        <div class="toolbar-actions"><el-button :icon="Plus" @click="showAreaDialog = true">新建景区</el-button><el-button :icon="Plus" @click="showBaseDialog = true">新建资料分组</el-button><el-button type="primary" :icon="Plus" @click="showProfileDialog = true">新建问答方案</el-button></div>
      </section>

      <section class="knowledge-control-grid">
        <article class="workspace-panel selector-panel"><span>1 · 景区</span><el-select v-model="selectedAreaId" placeholder="选择景区" @change="refreshProfiles"><el-option v-for="area in areas" :key="area.id" :label="area.name" :value="area.id" /></el-select><small>{{ selectedArea?.code }} · {{ selectedArea?.is_enabled ? '已启用' : '已停用' }}</small></article>
        <article class="workspace-panel selector-panel"><span>2 · 问答方案</span><el-select v-model="selectedProfileId" placeholder="选择问答方案"><el-option v-for="profile in profiles" :key="profile.id" :label="`${profile.name}（${profile.status === 'active' ? '使用中' : profile.status === 'draft' ? '草稿' : '已归档'}）`" :value="profile.id" /></el-select><small>选择要预览或调整的回答方案</small></article>
        <article class="workspace-panel selector-panel"><span>3 · 资料分组</span><el-select v-model="selectedBaseId" placeholder="选择资料分组" @change="changeKnowledgeBase"><el-option v-for="base in bases" :key="base.id" :label="base.name" :value="base.id" /></el-select><small>选择资料的归属位置</small></article>
      </section>

      <section class="profile-section"><div class="section-heading"><div><p class="eyebrow">问答方案</p><h2>各景区使用情况</h2></div></div><div class="profile-grid"><article v-for="profile in profiles" :key="profile.id" class="profile-card" :class="{ active: profile.status === 'active' }"><div class="profile-card-head"><el-tag :type="profile.status === 'active' ? 'success' : profile.status === 'draft' ? 'warning' : 'info'">{{ profile.status === 'active' ? '使用中' : profile.status === 'draft' ? '草稿' : '已归档' }}</el-tag><strong class="profile-reference-count">每次最多参考 {{ profile.top_k }} 段资料</strong></div><h3>{{ profile.name }}</h3><p>{{ profile.knowledge_base_bindings.filter((binding) => binding.is_enabled).map((binding) => binding.knowledge_base?.name).join(' · ') || '尚未关联资料分组' }}</p><small class="profile-explanation">游客提问时，讲解员会从这些资料中选择最相关的内容作为回答依据。</small><el-button v-if="profile.status !== 'active'" size="small" type="primary" plain @click="activate(profile)">启用此方案</el-button></article></div></section>

      <section class="knowledge-two-column">
        <article class="workspace-panel upload-panel">
          <div class="section-heading">
            <div><p class="eyebrow">资料维护</p><h2>上传景区资料</h2></div>
            <div class="ingest-actions">
              <span v-if="pollingDocuments" class="live-poll-indicator"><i />正在整理</span>
              <el-button :icon="RefreshRight" text @click="refreshDocuments">刷新</el-button>
            </div>
          </div>
          <p>支持 DOCX、TXT、可提取文字的 PDF；扫描 PDF 会提示先 OCR。单文件最大 20 MB。</p>
          <div class="upload-row">
            <input ref="fileInput" accept=".docx,.txt,.pdf" type="file" @change="selectFile" />
            <el-button type="primary" :icon="UploadFilled" :loading="uploading" @click="upload">{{ uploading ? `上传中 ${uploadPercent}%` : '上传并整理' }}</el-button>
          </div>
          <el-progress v-if="uploading" :percentage="uploadPercent" :stroke-width="5" :show-text="false" class="upload-progress" />
          <el-table :data="documents" size="small" max-height="360" empty-text="当前分组还没有资料">
            <el-table-column prop="original_filename" label="资料" min-width="155" show-overflow-tooltip />
            <el-table-column label="状态" width="92">
              <template #default="{ row }"><span class="document-status" :class="`is-${row.status}`"><i />{{ statusLabel(row.status) }}</span></template>
            </el-table-column>
            <el-table-column label="处理进度" min-width="155">
              <template #default="{ row }">
                <div class="document-progress"><el-progress :percentage="documentProgress(row)" :stroke-width="5" :show-text="false" /><small>已整理 {{ row.embedding_count }} / {{ row.chunk_count }} 段内容</small></div>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="142" fixed="right">
              <template #default="{ row }">
                <el-button size="small" text :disabled="row.status === 'pending' || row.status === 'indexing'" @click="reindex(row)">重新整理</el-button>
                <el-button size="small" text type="danger" :icon="Delete" :loading="deletingDocumentId === row.id" :disabled="row.status === 'pending' || row.status === 'indexing'" @click="removeDocument(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <p v-for="document in documents.filter((item) => item.error_message)" :key="document.id" class="error-text">{{ document.original_filename }}：{{ document.error_message }}</p>
        </article>

        <article class="workspace-panel preview-panel-rag">
          <div class="section-heading"><div><p class="eyebrow">发布前检查</p><h2>测试游客问答</h2></div></div>
          <el-input v-model="previewQuery" type="textarea" :rows="3" maxlength="2000" show-word-limit placeholder="输入要验证的导览问题" @keyup.ctrl.enter="searchPreview" />
          <el-button type="primary" :icon="Search" class="preview-button" :loading="previewLoading" @click="searchPreview">查看回答效果</el-button>
          <el-skeleton v-if="previewLoading" :rows="3" animated class="answer-skeleton" />
          <div v-if="preview" class="preview-result">
            <article class="ai-answer-card" :class="{ 'is-failed': preview.answer_status === 'failed' }">
              <div class="ai-answer-heading">
                <span class="ai-answer-icon"><el-icon><MagicStick /></el-icon></span>
                <div><small>游客端回答示例</small><strong>讲解员回答</strong></div>
                <span v-if="preview.answer_duration_ms" class="ai-latency">{{ (preview.answer_duration_ms / 1000).toFixed(1) }}s</span>
              </div>
              <p v-if="preview.ai_answer" class="ai-answer-content">{{ preview.ai_answer }}</p>
              <p v-else class="ai-answer-error">暂时无法生成回答：{{ preview.answer_error || '讲解服务暂时不可用' }}</p>
            </article>
            <p class="retrieval-summary">本次参考：{{ preview.knowledge_bases.join(' · ') }}，共找到 {{ preview.hits.length }} 段相关内容</p>
            <article v-for="(hit, index) in preview.hits" :key="hit.chunk_id" class="retrieval-hit">
              <div><span><el-tag size="small">资料 {{ index + 1 }}</el-tag><el-tag size="small" type="info">{{ hit.knowledge_base_name }}</el-tag></span><span>匹配程度 {{ Math.round(hit.score * 100) }}%</span></div>
              <strong>{{ hit.spot_name || hit.section || '资料片段' }}</strong>
              <p>{{ hit.content }}</p>
              <small>{{ hit.source_locator || '景区资料' }}</small>
            </article>
          </div>
        </article>
      </section>
    </div>

    <el-dialog v-model="showAreaDialog" title="新建景区" width="420px"><el-form label-position="top"><el-form-item label="景区编码"><el-input v-model="areaForm.code" placeholder="例如 lingshan-new" /></el-form-item><el-form-item label="景区名称"><el-input v-model="areaForm.name" /></el-form-item><el-form-item label="简介"><el-input v-model="areaForm.description" type="textarea" /></el-form-item></el-form><template #footer><el-button @click="showAreaDialog = false">取消</el-button><el-button type="primary" @click="createArea">创建</el-button></template></el-dialog>
    <el-dialog v-model="showBaseDialog" title="新建资料分组" width="420px"><el-form label-position="top"><el-form-item label="分组编码"><el-input v-model="baseForm.code" placeholder="例如 lingshan-guide" /></el-form-item><el-form-item label="分组名称"><el-input v-model="baseForm.name" /></el-form-item><el-form-item label="说明"><el-input v-model="baseForm.description" type="textarea" /></el-form-item></el-form><template #footer><el-button @click="showBaseDialog = false">取消</el-button><el-button type="primary" @click="createBase">创建</el-button></template></el-dialog>
    <el-dialog v-model="showProfileDialog" title="新建问答方案" width="500px"><el-form label-position="top"><el-form-item label="方案名称"><el-input v-model="profileForm.name" placeholder="例如 灵山春季活动草稿" /></el-form-item><el-form-item label="状态"><el-radio-group v-model="profileForm.status"><el-radio value="draft">保存为草稿</el-radio><el-radio value="active">创建后启用</el-radio></el-radio-group></el-form-item><el-form-item label="每次回答参考资料数"><div class="form-field-with-help"><el-input-number v-model="profileForm.top_k" :min="1" :max="20" /><small>系统会选择相应数量的相关内容辅助回答，一般保持 5 即可。</small></div></el-form-item><el-form-item label="关联资料分组"><el-checkbox-group v-model="profileForm.baseIds"><el-checkbox v-for="base in bases" :key="base.id" :value="base.id">{{ base.name }}</el-checkbox></el-checkbox-group></el-form-item></el-form><template #footer><el-button @click="showProfileDialog = false">取消</el-button><el-button type="primary" @click="createProfile">创建</el-button></template></el-dialog>
  </AppLayout>
</template>
