<script setup lang="ts">
import { Delete, EditPen, Microphone, StarFilled, UploadFilled, User } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref, watch } from 'vue'

import { avatarApi, type AvatarGender, type DigitalHuman, type ScenicAvatar, type VoiceOption } from '@/api/avatar'
import { knowledgeApi, type ScenicArea } from '@/api/knowledge'
import AppLayout from '@/layouts/AppLayout.vue'

const scenicAreas = ref<ScenicArea[]>([])
const selectedScenicAreaId = ref<number>()
const scenicAvatars = ref<ScenicAvatar[]>([])
const humans = ref<DigitalHuman[]>([])
const voices = ref<VoiceOption[]>([])
const loading = ref(false)
const humanDialogVisible = ref(false)
const variantDialogVisible = ref(false)
const editingHumanId = ref<number>()
const selectedFile = ref<File>()
const uploadInput = ref<HTMLInputElement>()

const selectedArea = computed(() => scenicAreas.value.find((area) => area.id === selectedScenicAreaId.value))
const activeCount = computed(() => scenicAvatars.value.filter((avatar) => avatar.is_enabled).length)

const humanForm = reactive({
  name: '',
  gender: 'female' as AvatarGender,
  role_title: '',
  introduction: '',
  tts_voice: '',
  tts_instructions: '',
  is_enabled: true,
})

const variantForm = reactive({
  digitalHumanId: 0,
  outfitName: '',
  version: 'v1',
  thumbnailUrl: '',
  isEnabled: true,
  isDefault: false,
  sortOrder: 0,
})

function errorText(error: unknown, fallback: string) {
  return (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || fallback
}

function resetHumanForm(human?: DigitalHuman) {
  editingHumanId.value = human?.id
  humanForm.name = human?.name || ''
  humanForm.gender = human?.gender || 'female'
  humanForm.role_title = human?.role_title || ''
  humanForm.introduction = human?.introduction || ''
  humanForm.tts_voice = human?.tts_voice || voices.value[0]?.value || ''
  humanForm.tts_instructions = human?.tts_instructions || ''
  humanForm.is_enabled = human?.is_enabled ?? true
}

function resetVariantForm() {
  variantForm.digitalHumanId = humans.value[0]?.id || 0
  variantForm.outfitName = ''
  variantForm.version = 'v1'
  variantForm.thumbnailUrl = ''
  variantForm.isEnabled = true
  variantForm.isDefault = scenicAvatars.value.every((avatar) => !avatar.is_default)
  variantForm.sortOrder = scenicAvatars.value.length
  selectedFile.value = undefined
  if (uploadInput.value) uploadInput.value.value = ''
}

async function loadData() {
  loading.value = true
  try {
    const [areasResponse, humansResponse, voicesResponse] = await Promise.all([
      knowledgeApi.listScenicAreas(),
      avatarApi.listHumans(),
      avatarApi.listVoices(),
    ])
    scenicAreas.value = areasResponse.data
    humans.value = humansResponse.data
    voices.value = voicesResponse.data
    if (!selectedScenicAreaId.value) selectedScenicAreaId.value = scenicAreas.value[0]?.id
    await loadScenicAvatars()
  } catch (error) {
    ElMessage.error(errorText(error, '数字人配置加载失败'))
  } finally {
    loading.value = false
  }
}

async function loadScenicAvatars() {
  if (!selectedScenicAreaId.value) {
    scenicAvatars.value = []
    return
  }
  scenicAvatars.value = (await avatarApi.listScenicConfigs(selectedScenicAreaId.value)).data
}

async function saveHuman() {
  if (!humanForm.name.trim() || !humanForm.role_title.trim() || !humanForm.tts_voice) {
    ElMessage.warning('请填写名称、角色定位和系统音色')
    return
  }
  const payload = {
    name: humanForm.name.trim(),
    gender: humanForm.gender,
    role_title: humanForm.role_title.trim(),
    introduction: humanForm.introduction.trim() || null,
    tts_voice: humanForm.tts_voice,
    tts_instructions: humanForm.tts_instructions.trim() || null,
  }
  try {
    if (editingHumanId.value) {
      await avatarApi.updateHuman(editingHumanId.value, { ...payload, is_enabled: humanForm.is_enabled })
    } else {
      await avatarApi.createHuman(payload)
    }
    humanDialogVisible.value = false
    await loadData()
    ElMessage.success('数字人资料已保存')
  } catch (error) {
    ElMessage.error(errorText(error, '数字人资料保存失败'))
  }
}

function onFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  selectedFile.value = target.files?.[0]
}

async function uploadVariant() {
  if (!selectedScenicAreaId.value || !variantForm.digitalHumanId || !variantForm.outfitName.trim() || !selectedFile.value) {
    ElMessage.warning('请选择人物、填写服装名称并上传 VRM 文件')
    return
  }
  try {
    await avatarApi.uploadVariant({
      digitalHumanId: variantForm.digitalHumanId,
      scenicAreaId: selectedScenicAreaId.value,
      outfitName: variantForm.outfitName.trim(),
      version: variantForm.version.trim() || 'v1',
      thumbnailUrl: variantForm.thumbnailUrl.trim() || undefined,
      isEnabled: variantForm.isEnabled,
      isDefault: variantForm.isDefault,
      sortOrder: variantForm.sortOrder,
      file: selectedFile.value,
    })
    variantDialogVisible.value = false
    await loadData()
    ElMessage.success('VRM 外观已上传并加入当前景区')
  } catch (error) {
    ElMessage.error(errorText(error, 'VRM 上传失败'))
  }
}

async function updateConfig(avatar: ScenicAvatar, patch: { is_enabled?: boolean; is_default?: boolean; sort_order?: number }) {
  try {
    await avatarApi.updateScenicConfig(avatar.config_id, patch)
    await loadScenicAvatars()
  } catch (error) {
    ElMessage.error(errorText(error, '景区上架配置更新失败'))
  }
}

async function toggleHuman(human: DigitalHuman) {
  try {
    await avatarApi.updateHuman(human.id, { is_enabled: !human.is_enabled })
    await loadData()
  } catch (error) {
    ElMessage.error(errorText(error, '人物状态更新失败'))
  }
}

async function removeHuman(human: DigitalHuman) {
  try {
    await ElMessageBox.confirm(`将删除“${human.name}”及其所有外观文件，此操作不可恢复。`, '删除数字人', { type: 'warning' })
    await avatarApi.deleteHuman(human.id)
    await loadData()
    ElMessage.success('数字人已删除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(errorText(error, '数字人删除失败'))
  }
}

async function removeVariant(avatar: ScenicAvatar) {
  try {
    await ElMessageBox.confirm(`删除“${avatar.name} / ${avatar.outfit_name}”外观文件？`, '删除外观', { type: 'warning' })
    await avatarApi.deleteVariant(avatar.id)
    await loadData()
    ElMessage.success('外观已删除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(errorText(error, '外观删除失败'))
  }
}

function openHumanDialog(human?: DigitalHuman) {
  resetHumanForm(human)
  humanDialogVisible.value = true
}

function openVariantDialog() {
  resetVariantForm()
  variantDialogVisible.value = true
}

function formatBytes(value: number) {
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

watch(selectedScenicAreaId, () => void loadScenicAvatars())
onMounted(() => void loadData())
</script>

<template>
  <AppLayout title="数字人管理" description="维护讲解员形象、声音和景区启用配置。" role-label="运营管理">
    <section v-loading="loading" class="avatar-management-page">
      <header class="avatar-management-hero">
        <div>
          <p class="eyebrow">LINGSHAN AVATAR STUDIO</p>
          <h2>让每一位讲解员，都有自己的文化气质。</h2>
          <p>人物负责声音与讲解风格，外观版本负责服装与 VRM 模型；仅上架版本会出现在游客端。</p>
        </div>
        <div class="avatar-hero-actions">
          <el-button :icon="User" @click="openHumanDialog()">新建人物</el-button>
          <el-button type="primary" :icon="UploadFilled" :disabled="!selectedScenicAreaId || !humans.length" @click="openVariantDialog">上传 VRM 外观</el-button>
        </div>
      </header>

      <section class="avatar-control-strip">
        <div>
          <span>当前景区</span>
          <el-select v-model="selectedScenicAreaId" placeholder="选择景区">
            <el-option v-for="area in scenicAreas" :key="area.id" :label="area.name" :value="area.id" />
          </el-select>
        </div>
        <div class="avatar-control-summary">
          <strong>{{ activeCount }}</strong><span>个游客可用形象</span>
          <i />
          <span>{{ selectedArea?.name || '未选择景区' }}</span>
        </div>
      </section>

      <section class="avatar-stage-section">
        <div class="avatar-section-heading">
          <div><p class="eyebrow">PUBLISHED VARIANTS</p><h3>景区上架外观</h3></div>
          <small>设为默认后，游客首次进入会优先看到该讲解员。</small>
        </div>
        <div v-if="scenicAvatars.length" class="avatar-variant-grid">
          <article v-for="avatar in scenicAvatars" :key="avatar.config_id" class="avatar-variant-card" :class="{ disabled: !avatar.is_enabled }">
            <div class="avatar-card-visual" :class="`is-${avatar.gender}`">
              <img v-if="avatar.thumbnail_url" :src="avatar.thumbnail_url" :alt="avatar.name" />
              <span v-else>{{ avatar.name.slice(-1) }}</span>
              <em v-if="avatar.is_default"><StarFilled /> 默认</em>
              <b>{{ avatar.gender === 'female' ? '女' : avatar.gender === 'male' ? '男' : '未设' }}</b>
            </div>
            <div class="avatar-card-body">
              <div><p>{{ avatar.role_title }}</p><h4>{{ avatar.name }}</h4></div>
              <span class="avatar-outfit">{{ avatar.outfit_name }} · {{ avatar.version }}</span>
              <p class="avatar-file-info">{{ formatBytes(avatar.file_size) }} · VRM 1.0</p>
              <div class="avatar-card-controls">
                <el-switch :model-value="avatar.is_enabled" active-text="游客可见" inactive-text="已下架" @change="updateConfig(avatar, { is_enabled: Boolean($event) })" />
                <el-button v-if="!avatar.is_default && avatar.is_enabled" size="small" plain :icon="StarFilled" @click="updateConfig(avatar, { is_default: true })">设为默认</el-button>
              </div>
              <div class="avatar-card-footer">
                <label>排序 <el-input-number :model-value="avatar.sort_order" size="small" :min="-1000" :max="1000" controls-position="right" @change="updateConfig(avatar, { sort_order: Number($event || 0) })" /></label>
                <el-button text type="danger" :icon="Delete" @click="removeVariant(avatar)">删除外观</el-button>
              </div>
            </div>
          </article>
        </div>
        <el-empty v-else description="当前景区暂无数字人形象"><el-button type="primary" @click="openVariantDialog">添加形象</el-button></el-empty>
      </section>

      <section class="avatar-people-section">
        <div class="avatar-section-heading"><div><p class="eyebrow">GUIDE IDENTITIES</p><h3>人物与声音档案</h3></div><small>停用人物后，其所有上架外观都会从游客端隐藏。</small></div>
        <div class="avatar-people-grid">
          <article v-for="human in humans" :key="human.id" class="avatar-person-card" :class="{ disabled: !human.is_enabled }">
            <span class="avatar-person-mark">{{ human.name.slice(-1) }}</span>
            <div class="avatar-person-main"><p>{{ human.gender === 'female' ? '女性讲解员' : human.gender === 'male' ? '男性讲解员' : '数字讲解员' }}</p><h4>{{ human.name }}</h4><strong>{{ human.role_title }}</strong></div>
            <p>{{ human.introduction || '暂未填写人物介绍。' }}</p>
            <div class="avatar-person-voice"><Microphone /><span>{{ human.tts_voice }}</span><small>{{ human.tts_instructions || '采用默认景区讲解语气' }}</small></div>
            <footer><el-switch :model-value="human.is_enabled" active-text="启用" inactive-text="停用" @change="toggleHuman(human)" /><span /><el-button text :icon="EditPen" @click="openHumanDialog(human)">编辑</el-button><el-button text type="danger" :icon="Delete" @click="removeHuman(human)">删除</el-button></footer>
          </article>
        </div>
      </section>
    </section>

    <el-dialog v-model="humanDialogVisible" :title="editingHumanId ? '编辑数字人资料' : '新建数字人'" width="620px" destroy-on-close>
      <el-form label-position="top" class="avatar-form">
        <div class="avatar-form-two-column"><el-form-item label="中文名字"><el-input v-model="humanForm.name" placeholder="例如：沈清莲" /></el-form-item><el-form-item label="性别"><el-select v-model="humanForm.gender"><el-option label="女性" value="female" /><el-option label="男性" value="male" /><el-option label="未指定" value="unspecified" /></el-select></el-form-item></div>
        <el-form-item label="角色定位"><el-input v-model="humanForm.role_title" placeholder="例如：灵山文化讲解员" /></el-form-item>
        <el-form-item label="人物介绍"><el-input v-model="humanForm.introduction" type="textarea" :rows="2" /></el-form-item>
        <div class="avatar-form-two-column"><el-form-item label="系统音色"><el-select v-model="humanForm.tts_voice"><el-option v-for="voice in voices" :key="voice.value" :label="voice.label" :value="voice.value" /></el-select></el-form-item><el-form-item v-if="editingHumanId" label="人物状态"><el-switch v-model="humanForm.is_enabled" active-text="启用" inactive-text="停用" /></el-form-item></div>
        <el-form-item label="讲解风格指令"><el-input v-model="humanForm.tts_instructions" type="textarea" :rows="3" placeholder="例如：语速适中，温和、清晰地介绍灵山文化。" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="humanDialogVisible = false">取消</el-button><el-button type="primary" @click="saveHuman">保存人物</el-button></template>
    </el-dialog>

    <el-dialog v-model="variantDialogVisible" title="上传 VRM 外观版本" width="620px" destroy-on-close>
      <el-form label-position="top" class="avatar-form">
        <el-form-item label="归属人物"><el-select v-model="variantForm.digitalHumanId" filterable><el-option v-for="human in humans" :key="human.id" :label="`${human.name} · ${human.role_title}`" :value="human.id" /></el-select></el-form-item>
        <div class="avatar-form-two-column"><el-form-item label="服装/外观名称"><el-input v-model="variantForm.outfitName" placeholder="例如：浅青新中式" /></el-form-item><el-form-item label="版本"><el-input v-model="variantForm.version" /></el-form-item></div>
        <el-form-item label="VRM 文件（最大 80MB）"><input ref="uploadInput" class="avatar-file-input" type="file" accept=".vrm,model/gltf-binary" @change="onFileChange" /><small v-if="selectedFile">已选择：{{ selectedFile.name }}（{{ formatBytes(selectedFile.size) }}）</small></el-form-item>
        <el-form-item label="缩略图地址（可选）"><el-input v-model="variantForm.thumbnailUrl" placeholder="可填写图片 URL，未填写时显示人物字标" /></el-form-item>
        <div class="avatar-form-inline"><el-switch v-model="variantForm.isEnabled" active-text="上传后立即上架" inactive-text="保存为下架" /><el-switch v-model="variantForm.isDefault" :disabled="!variantForm.isEnabled" active-text="设为默认" /><el-form-item label="排序"><el-input-number v-model="variantForm.sortOrder" :min="-1000" :max="1000" /></el-form-item></div>
      </el-form>
      <template #footer><el-button @click="variantDialogVisible = false">取消</el-button><el-button type="primary" :icon="UploadFilled" @click="uploadVariant">上传并保存</el-button></template>
    </el-dialog>
  </AppLayout>
</template>
