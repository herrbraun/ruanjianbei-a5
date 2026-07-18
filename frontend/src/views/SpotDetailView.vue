<script setup lang="ts">
import { ArrowLeft, Headset, VideoPlay } from '@element-plus/icons-vue'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { getSpot, type ScenicSpot } from '@/api/spots'
import AppLayout from '@/layouts/AppLayout.vue'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const spot = ref<ScenicSpot | null>(null)
const failedImages = ref(new Set<string>())
const imageAssets = computed(() => {
  if (!spot.value) return []
  const urls = [spot.value.cover_image_url, ...spot.value.media_assets.filter((asset) => asset.media_type === 'image').map((asset) => asset.url)].filter(Boolean) as string[]
  return [...new Set(urls)]
})
const otherAssets = computed(() => spot.value?.media_assets.filter((asset) => asset.media_type !== 'image') || [])

async function loadSpot() {
  const id = Number(route.params.id)
  if (!Number.isFinite(id)) { ElMessage.error('没有找到这个景点'); router.push('/visitor/spots'); return }
  loading.value = true
  try { spot.value = (await getSpot(id)).data }
  catch { ElMessage.error('景点详情加载失败，请返回列表重试'); router.push('/visitor/spots') }
  finally { loading.value = false }
}

function markImageFailed(url: string) { failedImages.value = new Set([...failedImages.value, url]) }

onMounted(loadSpot)
</script>

<template>
  <AppLayout title="景点介绍" description="了解景点故事和游览须知。" role-label="景区导览">
    <template #actions><el-button :icon="ArrowLeft" @click="router.push('/visitor/spots')">返回景点列表</el-button></template>
    <div v-if="loading" class="detail-loading"><el-skeleton :rows="8" animated /></div>
    <article v-else-if="spot" class="spot-detail">
      <section class="detail-visual">
        <div v-if="imageAssets.some((url) => !failedImages.has(url))" class="detail-gallery">
          <img v-for="url in imageAssets.filter((item) => !failedImages.has(item))" :key="url" :src="url" :alt="`${spot.name}景点图片`" loading="lazy" @error="markImageFailed(url)" />
        </div>
        <div v-else class="detail-image-placeholder"><span>{{ spot.name.slice(0, 1) }}</span><strong>{{ spot.name }}</strong><small>{{ spot.scenic_area }} · 暂无图片</small></div>
      </section>

      <section class="detail-intro">
        <div class="detail-kicker"><span>{{ spot.scenic_area }}</span></div>
        <h2>{{ spot.name }}</h2><p class="detail-summary">{{ spot.summary }}</p>
        <div class="tag-row"><el-tag v-for="tag in spot.tags" :key="tag" effect="plain">{{ tag }}</el-tag></div>
        <dl class="info-list"><div><dt>所在位置</dt><dd>{{ spot.location || '请以景区现场指引为准' }}</dd></div><div><dt>开放安排</dt><dd>{{ spot.opening_hours || '请以景区当日公告为准' }}</dd></div><div><dt>建议游览</dt><dd>{{ spot.recommended_duration_minutes }} 分钟</dd></div><div><dt>景点类型</dt><dd>{{ spot.spot_type === 'attraction' ? '景点' : spot.spot_type === 'area' ? '游览区域' : '服务设施' }}</dd></div></dl>
      </section>

      <section class="detail-content">
        <div class="content-section"><span>景点介绍</span><h3>了解 {{ spot.name }}</h3><p>{{ spot.description }}</p></div>
        <div v-if="spot.landscape_parameters" class="content-section"><span>建筑与景观</span><h3>形制与特色</h3><p>{{ spot.landscape_parameters }}</p></div>
        <div v-if="spot.cultural_context" class="content-section"><span>文化内涵</span><h3>景点背后的故事</h3><p>{{ spot.cultural_context }}</p></div>
        <div v-if="spot.highlights" class="content-section"><span>游玩亮点</span><h3>值得体验</h3><p>{{ spot.highlights }}</p></div>
        <div v-if="spot.notes" class="content-section"><span>游览提示</span><h3>出发前留意</h3><p>{{ spot.notes }}</p></div>
        <div v-if="otherAssets.length" class="content-section"><span>更多内容</span><h3>视频与语音介绍</h3><div class="asset-links"><a v-for="asset in otherAssets" :key="asset.id" :href="asset.url" target="_blank" rel="noreferrer"><el-icon><VideoPlay v-if="asset.media_type === 'video'" /><Headset v-else /></el-icon><span>{{ asset.description || (asset.media_type === 'video' ? '观看景点视频' : '收听景点介绍') }}</span></a></div></div>
      </section>
    </article>
  </AppLayout>
</template>
