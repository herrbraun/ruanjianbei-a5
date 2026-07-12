<script setup lang="ts">
import { Edit, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import {
  createAdminSpot,
  getAdminSpots,
  updateAdminSpot,
  updateAdminSpotStatus,
  type ScenicSpot,
  type SpotPayload,
  type SpotStatus,
  type SpotType,
} from '@/api/spots'
import AppLayout from '@/layouts/AppLayout.vue'

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const spots = ref<ScenicSpot[]>([])
const initialSnapshot = ref('')
const form = reactive({
  external_id: '', scenic_area: '灵山胜境', spot_type: 'attraction' as SpotType, name: '', summary: '', description: '',
  location: '', opening_hours: '', landscape_parameters: '', cultural_context: '', highlights: '', notes: '', source_name: '',
  recommended_duration_minutes: 30, priority: 50, status: 'enabled' as SpotStatus, cover_image_url: '', tagsText: '',
})

function resetForm() {
  editingId.value = null
  Object.assign(form, {
    external_id: '', scenic_area: '灵山胜境', spot_type: 'attraction', name: '', summary: '', description: '', location: '',
    opening_hours: '', landscape_parameters: '', cultural_context: '', highlights: '', notes: '', source_name: '',
    recommended_duration_minutes: 30, priority: 50, status: 'enabled', cover_image_url: '', tagsText: '',
  })
}

function buildPayload(): SpotPayload {
  return {
    external_id: form.external_id.trim() || null,
    scenic_area: form.scenic_area.trim(),
    spot_type: form.spot_type,
    name: form.name.trim(), summary: form.summary.trim(), description: form.description.trim(),
    location: form.location.trim() || null, opening_hours: form.opening_hours.trim() || null,
    landscape_parameters: form.landscape_parameters.trim() || null, cultural_context: form.cultural_context.trim() || null,
    highlights: form.highlights.trim() || null, notes: form.notes.trim() || null, source_name: form.source_name.trim() || null,
    recommended_duration_minutes: form.recommended_duration_minutes, priority: form.priority, status: form.status,
    cover_image_url: form.cover_image_url.trim() || null,
    tags: form.tagsText.split(/[,，]/).map((tag) => tag.trim()).filter(Boolean),
  }
}

async function loadSpots() {
  loading.value = true
  try { spots.value = (await getAdminSpots()).data }
  catch { ElMessage.error('景点管理列表加载失败') }
  finally { loading.value = false }
}

function openCreateDialog() { resetForm(); initialSnapshot.value = JSON.stringify(form); dialogVisible.value = true }

function openEditDialog(spot: ScenicSpot) {
  editingId.value = spot.id
  Object.assign(form, {
    external_id: spot.external_id || '', scenic_area: spot.scenic_area, spot_type: spot.spot_type, name: spot.name,
    summary: spot.summary, description: spot.description, location: spot.location || '', opening_hours: spot.opening_hours || '',
    landscape_parameters: spot.landscape_parameters || '', cultural_context: spot.cultural_context || '',
    highlights: spot.highlights || '', notes: spot.notes || '', source_name: spot.source_name || '',
    recommended_duration_minutes: spot.recommended_duration_minutes, priority: spot.priority, status: spot.status,
    cover_image_url: spot.cover_image_url || '', tagsText: spot.tags.join('，'),
  })
  initialSnapshot.value = JSON.stringify(form)
  dialogVisible.value = true
}

async function handleDrawerClose(done: () => void) {
  if (JSON.stringify(form) === initialSnapshot.value) { done(); return }
  try { await ElMessageBox.confirm('当前修改尚未保存，确认关闭？', '放弃未保存修改', { type: 'warning', confirmButtonText: '放弃修改', cancelButtonText: '继续编辑' }); done() }
  catch { return }
}

async function saveSpot() {
  if (!form.scenic_area.trim() || !form.name.trim() || !form.summary.trim() || !form.description.trim()) {
    ElMessage.warning('请填写所属景区、名称、简介和详情')
    return
  }
  saving.value = true
  try {
    if (editingId.value) await updateAdminSpot(editingId.value, buildPayload())
    else await createAdminSpot(buildPayload())
    ElMessage.success('景点已保存')
    initialSnapshot.value = JSON.stringify(form)
    dialogVisible.value = false
    await loadSpots()
  } catch { ElMessage.error('景点保存失败，请检查景点编号是否重复') }
  finally { saving.value = false }
}

async function toggleStatus(spot: ScenicSpot) {
  const nextStatus: SpotStatus = spot.status === 'enabled' ? 'disabled' : 'enabled'
  try {
    await updateAdminSpotStatus(spot.id, nextStatus)
    ElMessage.success(nextStatus === 'enabled' ? '景点已启用' : '景点已停用')
    await loadSpots()
  } catch { ElMessage.error('状态更新失败') }
}

onMounted(loadSpots)
</script>

<template>
  <AppLayout title="景点管理" description="维护景点、展区和服务点信息。" role-label="运营管理">
    <template #actions><el-button type="primary" :icon="Plus" @click="openCreateDialog">新增景点</el-button></template>

    <section class="data-section"><div class="data-section-header"><div><span>景点列表</span><h2>全部景点</h2></div><strong>{{ spots.length }} 个</strong></div>

    <el-table v-loading="loading" :data="spots" class="admin-table desktop-table">
      <el-table-column prop="external_id" label="景点编号" width="100" />
      <el-table-column prop="scenic_area" label="所属景区" min-width="150" />
      <el-table-column prop="name" label="名称" min-width="150" />
      <el-table-column prop="spot_type" label="类型" width="100" />
      <el-table-column label="标签" min-width="180"><template #default="{ row }"><div class="tag-row"><el-tag v-for="tag in row.tags" :key="tag" size="small">{{ tag }}</el-tag></div></template></el-table-column>
      <el-table-column prop="recommended_duration_minutes" label="停留分钟" width="100" />
      <el-table-column prop="priority" label="优先级" width="80" />
      <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag :type="row.status === 'enabled' ? 'success' : 'info'">{{ row.status === 'enabled' ? '启用' : '停用' }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="190" fixed="right"><template #default="{ row }"><el-button size="small" :icon="Edit" @click="openEditDialog(row)">编辑</el-button><el-button size="small" plain @click="toggleStatus(row)">{{ row.status === 'enabled' ? '停用' : '启用' }}</el-button></template></el-table-column>
    </el-table>
    <div v-loading="loading" class="mobile-record-list"><article v-for="spot in spots" :key="spot.id" class="mobile-record-card"><header><div><span>{{ spot.external_id || `#${spot.id}` }}</span><h3>{{ spot.name }}</h3></div><el-tag :type="spot.status === 'enabled' ? 'success' : 'info'">{{ spot.status === 'enabled' ? '启用' : '停用' }}</el-tag></header><p>{{ spot.scenic_area }} · {{ spot.recommended_duration_minutes }} 分钟 · 优先级 {{ spot.priority }}</p><div class="tag-row"><el-tag v-for="tag in spot.tags.slice(0, 4)" :key="tag" size="small" effect="plain">{{ tag }}</el-tag></div><footer><el-button :icon="Edit" @click="openEditDialog(spot)">编辑</el-button><el-button plain @click="toggleStatus(spot)">{{ spot.status === 'enabled' ? '停用' : '启用' }}</el-button></footer></article></div>
    </section>

    <el-drawer v-model="dialogVisible" :title="editingId ? '编辑景点' : '新增景点'" size="min(94vw, 720px)" :before-close="handleDrawerClose" class="record-drawer">
      <el-form label-position="top" class="drawer-form">
        <div class="form-section-title"><span>01</span><div><h3>基础信息</h3><p>设置景点名称、分类和介绍。</p></div></div>
        <div class="form-grid">
          <el-form-item label="景点编号"><el-input v-model="form.external_id" /></el-form-item>
          <el-form-item label="所属景区" required><el-input v-model="form.scenic_area" /></el-form-item>
          <el-form-item label="分类" required><el-select v-model="form.spot_type"><el-option label="景点" value="attraction" /><el-option label="展区" value="area" /><el-option label="服务点" value="service" /></el-select></el-form-item>
          <el-form-item label="名称" required><el-input v-model="form.name" /></el-form-item>
        </div>
        <el-form-item label="一句话简介" required><el-input v-model="form.summary" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="详细介绍" required><el-input v-model="form.description" type="textarea" :rows="5" /></el-form-item>
        <div class="form-section-title"><span>02</span><div><h3>文化内容</h3><p>展示景点特色、文化内涵和游玩亮点。</p></div></div>
        <el-form-item label="建筑与景观"><el-input v-model="form.landscape_parameters" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="文化内涵"><el-input v-model="form.cultural_context" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="游玩亮点"><el-input v-model="form.highlights" type="textarea" :rows="3" /></el-form-item>
        <div class="form-section-title"><span>03</span><div><h3>运营配置</h3><p>配置开放信息、路线权重和展示状态。</p></div></div>
        <div class="form-grid">
          <el-form-item label="位置"><el-input v-model="form.location" /></el-form-item>
          <el-form-item label="推荐停留分钟"><el-input-number v-model="form.recommended_duration_minutes" :min="5" :max="480" /></el-form-item>
          <el-form-item label="优先级"><el-input-number v-model="form.priority" :min="0" :max="100" /></el-form-item>
          <el-form-item label="状态"><el-radio-group v-model="form.status"><el-radio-button value="enabled">启用</el-radio-button><el-radio-button value="disabled">停用</el-radio-button></el-radio-group></el-form-item>
        </div>
        <el-form-item label="开放时间与活动"><el-input v-model="form.opening_hours" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.notes" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="封面图地址"><el-input v-model="form.cover_image_url" /></el-form-item>
        <el-form-item label="标签"><el-input v-model="form.tagsText" placeholder="用逗号分隔" /></el-form-item>
      </el-form>
      <template #footer><div class="drawer-footer"><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveSpot">保存景点</el-button></div></template>
    </el-drawer>
  </AppLayout>
</template>
