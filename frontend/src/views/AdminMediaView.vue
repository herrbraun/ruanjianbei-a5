<script setup lang="ts">
import { Delete, Edit, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import {
  createAdminMedia,
  deleteAdminMedia,
  getAdminMedia,
  getAdminSpots,
  updateAdminMedia,
  type MediaPayload,
  type MediaType,
  type ScenicSpot,
  type SpotMediaAsset,
  type SpotStatus,
} from '@/api/spots'
import AppLayout from '@/layouts/AppLayout.vue'

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const assets = ref<SpotMediaAsset[]>([])
const spots = ref<ScenicSpot[]>([])
const form = reactive({
  spot_id: undefined as number | undefined,
  media_type: 'image' as MediaType,
  url: '',
  description: '',
  sort_order: 0,
  status: 'enabled' as SpotStatus,
})

function resetForm() {
  editingId.value = null
  form.spot_id = spots.value[0]?.id
  form.media_type = 'image'
  form.url = ''
  form.description = ''
  form.sort_order = 0
  form.status = 'enabled'
}

async function loadData() {
  loading.value = true
  try {
    const [assetResponse, spotResponse] = await Promise.all([getAdminMedia(), getAdminSpots()])
    assets.value = assetResponse.data
    spots.value = spotResponse.data
  } catch {
    ElMessage.error('素材加载失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(asset: SpotMediaAsset) {
  editingId.value = asset.id
  form.spot_id = asset.spot_id
  form.media_type = asset.media_type
  form.url = asset.url
  form.description = asset.description || ''
  form.sort_order = asset.sort_order
  form.status = asset.status
  dialogVisible.value = true
}

async function save() {
  if (!form.spot_id || !form.url.trim()) {
    ElMessage.warning('请选择景点并填写素材地址')
    return
  }
  const payload: MediaPayload = {
    spot_id: form.spot_id,
    media_type: form.media_type,
    url: form.url.trim(),
    description: form.description.trim() || null,
    sort_order: form.sort_order,
    status: form.status,
  }
  saving.value = true
  try {
    if (editingId.value) await updateAdminMedia(editingId.value, payload)
    else await createAdminMedia(payload)
    dialogVisible.value = false
    ElMessage.success('素材已保存')
    await loadData()
  } catch {
    ElMessage.error('素材保存失败，请检查 URL 或是否重复')
  } finally {
    saving.value = false
  }
}

async function remove(asset: SpotMediaAsset) {
  try {
    await ElMessageBox.confirm(`确认删除“${asset.spot_name}”的这条素材？`, '删除素材', { type: 'warning' })
    await deleteAdminMedia(asset.id)
    ElMessage.success('素材已删除')
    await loadData()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('素材删除失败')
  }
}

onMounted(loadData)
</script>

<template>
  <AppLayout title="素材管理" description="维护景点图片、视频和音频。" role-label="运营管理">
    <template #actions><el-button type="primary" :icon="Plus" @click="openCreate">新增素材</el-button></template>
    <section class="data-section"><div class="data-section-header"><div><span>素材库</span><h2>全部素材</h2></div><strong>{{ assets.length }} 个</strong></div>

    <el-table v-loading="loading" :data="assets" class="admin-table desktop-table">
      <el-table-column prop="spot_name" label="景点" min-width="150" />
      <el-table-column prop="media_type" label="类型" width="90" />
      <el-table-column prop="url" label="素材地址" min-width="260" show-overflow-tooltip />
      <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
      <el-table-column prop="sort_order" label="排序" width="80" />
      <el-table-column prop="status" label="状态" width="90" />
      <el-table-column label="操作" width="150">
        <template #default="{ row }">
          <el-button :icon="Edit" size="small" @click="openEdit(row)">编辑</el-button>
          <el-button :icon="Delete" size="small" type="danger" text aria-label="删除素材" title="删除素材" @click="remove(row)" />
        </template>
      </el-table-column>
    </el-table>
    <div v-loading="loading" class="mobile-record-list"><article v-for="asset in assets" :key="asset.id" class="mobile-record-card"><header><div><span>{{ asset.media_type }}</span><h3>{{ asset.spot_name }}</h3></div><el-tag :type="asset.status === 'enabled' ? 'success' : 'info'">{{ asset.status === 'enabled' ? '启用' : '停用' }}</el-tag></header><p>{{ asset.description || '暂无描述' }}</p><a class="asset-url" :href="asset.url" target="_blank" rel="noreferrer">{{ asset.url }}</a><footer><el-button :icon="Edit" @click="openEdit(asset)">编辑</el-button><el-button :icon="Delete" type="danger" plain @click="remove(asset)">删除</el-button></footer></article></div>
    <el-empty v-if="!loading && assets.length === 0" description="暂未添加素材" />
    </section>

    <el-drawer v-model="dialogVisible" :title="editingId ? '编辑素材' : '新增素材'" size="min(94vw, 560px)">
      <el-form label-position="top" class="drawer-form">
        <el-form-item label="绑定景点" required>
          <el-select v-model="form.spot_id" filterable style="width: 100%">
            <el-option v-for="spot in spots" :key="spot.id" :label="`${spot.external_id || spot.id} · ${spot.name}`" :value="spot.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="素材类型" required>
          <el-select v-model="form.media_type" style="width: 100%">
            <el-option label="图片" value="image" />
            <el-option label="视频" value="video" />
            <el-option label="音频" value="audio" />
          </el-select>
        </el-form-item>
        <el-form-item label="素材地址" required><el-input v-model="form.url" placeholder="请输入 HTTP(S) 地址" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" /></el-form-item>
        <el-form-item label="排序"><el-input-number v-model="form.sort_order" :min="0" :max="1000" /></el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio-button value="enabled">启用</el-radio-button>
            <el-radio-button value="disabled">停用</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="drawer-footer"><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存素材</el-button></div>
      </template>
    </el-drawer>
  </AppLayout>
</template>
