<script setup lang="ts">
import { Camera, Lock, User } from '@element-plus/icons-vue'
import { isAxiosError } from 'axios'
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { changePassword, getInterestOptions, resolveAssetUrl, updateProfile, uploadAvatar } from '@/api/auth'
import InterestSelector from '@/components/InterestSelector.vue'
import AppLayout from '@/layouts/AppLayout.vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const fileInput = ref<HTMLInputElement | null>(null)
const interestOptions = ref<string[]>([])
const profileLoading = ref(false)
const passwordLoading = ref(false)
const avatarLoading = ref(false)
const optionLoading = ref(false)
const nickname = ref(authStore.user?.nickname || authStore.user?.username || '')
const selectedInterests = ref<string[]>([...(authStore.user?.interests || [])])
const passwordForm = reactive({ current: '', next: '', confirm: '' })
const avatarUrl = computed(() => resolveAssetUrl(authStore.user?.avatar_url))

async function loadOptions() {
  optionLoading.value = true
  try {
    interestOptions.value = (await getInterestOptions()).data.interests
  } catch {
    ElMessage.error('兴趣标签加载失败')
  } finally {
    optionLoading.value = false
  }
}

async function saveProfile() {
  if (!nickname.value.trim()) {
    ElMessage.warning('昵称不能为空')
    return
  }
  if (!selectedInterests.value.length) {
    ElMessage.warning('请至少选择一个兴趣标签')
    return
  }
  profileLoading.value = true
  try {
    const response = await updateProfile({ nickname: nickname.value.trim(), interests: selectedInterests.value })
    authStore.setUser(response.data)
    ElMessage.success('账号资料已更新')
  } catch {
    ElMessage.error('资料保存失败，请稍后重试')
  } finally {
    profileLoading.value = false
  }
}

function selectAvatar() {
  fileInput.value?.click()
}

async function handleAvatar(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
    ElMessage.warning('请选择 PNG、JPEG 或 WebP 图片')
    input.value = ''
    return
  }
  if (file.size > 5 * 1024 * 1024) {
    ElMessage.warning('头像图片不能超过 5 MB')
    input.value = ''
    return
  }
  avatarLoading.value = true
  try {
    const response = await uploadAvatar(file)
    authStore.setUser(response.data)
    ElMessage.success('头像已更新')
  } catch {
    ElMessage.error('头像上传失败，请检查图片后重试')
  } finally {
    avatarLoading.value = false
    input.value = ''
  }
}

async function savePassword() {
  if (!passwordForm.current) {
    ElMessage.warning('请输入当前密码')
    return
  }
  if (passwordForm.next.length < 8) {
    ElMessage.warning('新密码至少需要 8 位')
    return
  }
  if (passwordForm.next !== passwordForm.confirm) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  passwordLoading.value = true
  try {
    await changePassword({ current_password: passwordForm.current, new_password: passwordForm.next })
    passwordForm.current = ''
    passwordForm.next = ''
    passwordForm.confirm = ''
    ElMessage.success('密码已修改')
  } catch (error) {
    if (isAxiosError(error) && error.response?.status === 400) {
      ElMessage.error(error.response.data?.detail === 'Current password is incorrect' ? '当前密码不正确' : '新密码不能与当前密码相同')
    } else {
      ElMessage.error('密码修改失败，请稍后重试')
    }
  } finally {
    passwordLoading.value = false
  }
}

onMounted(loadOptions)
</script>

<template>
  <AppLayout title="账号管理" description="管理头像、昵称、兴趣偏好和登录密码。" role-label="个人中心">
    <div class="account-workspace">
      <aside class="profile-summary" aria-label="头像与账号">
        <div class="profile-avatar">
          <img v-if="avatarUrl" :src="avatarUrl" alt="当前头像">
          <el-icon v-else><User /></el-icon>
        </div>
        <strong>{{ authStore.user?.nickname }}</strong>
        <span>@{{ authStore.user?.username }}</span>
        <input ref="fileInput" class="visually-hidden" type="file" accept="image/png,image/jpeg,image/webp" @change="handleAvatar">
        <el-button :icon="Camera" :loading="avatarLoading" @click="selectAvatar">上传头像</el-button>
        <small>支持 PNG、JPEG、WebP，最大 5 MB</small>
      </aside>

      <div class="account-settings">
        <section class="account-section">
          <div class="section-heading compact"><div><span>基础资料</span><h2>账号信息</h2></div></div>
          <el-form label-position="top" class="account-form" @submit.prevent="saveProfile">
            <el-form-item label="账号名"><el-input :model-value="authStore.user?.username || ''" readonly><template #prefix><el-icon><User /></el-icon></template></el-input><p class="field-note">账号名用于登录，注册后不可修改。</p></el-form-item>
            <el-form-item label="用户昵称" required><el-input v-model="nickname" maxlength="100" show-word-limit placeholder="请输入昵称" /></el-form-item>
            <el-form-item label="兴趣标签" required>
              <div v-loading="optionLoading" class="interest-field"><InterestSelector v-model="selectedInterests" :options="interestOptions" :disabled="profileLoading" /><p class="selection-count">已选择 {{ selectedInterests.length }} / 8</p></div>
            </el-form-item>
            <el-button type="primary" :loading="profileLoading" @click="saveProfile">保存资料</el-button>
          </el-form>
        </section>

        <section class="account-section">
          <div class="section-heading compact"><div><span>账号安全</span><h2>修改密码</h2></div></div>
          <el-form label-position="top" class="account-form password-form" @submit.prevent="savePassword">
            <el-form-item label="当前密码" required><el-input v-model="passwordForm.current" :prefix-icon="Lock" type="password" show-password autocomplete="current-password" /></el-form-item>
            <el-form-item label="新密码" required><el-input v-model="passwordForm.next" :prefix-icon="Lock" type="password" show-password autocomplete="new-password" placeholder="至少 8 位" /></el-form-item>
            <el-form-item label="确认新密码" required><el-input v-model="passwordForm.confirm" :prefix-icon="Lock" type="password" show-password autocomplete="new-password" /></el-form-item>
            <el-button type="primary" plain :loading="passwordLoading" @click="savePassword">修改密码</el-button>
          </el-form>
        </section>
      </div>
    </div>
  </AppLayout>
</template>
