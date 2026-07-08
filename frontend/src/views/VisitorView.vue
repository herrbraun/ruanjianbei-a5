<script setup lang="ts">
import AppLayout from '@/layouts/AppLayout.vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
</script>

<template>
  <AppLayout title="游客端" description="这里将承载数字人导游、景区问答、语音输入和个性化路线推荐。" role-label="当前身份：游客">
    <section class="workspace-grid">
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
