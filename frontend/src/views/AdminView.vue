<script setup lang="ts">
import { Collection } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

import AppLayout from '@/layouts/AppLayout.vue'

const router = useRouter()
</script>

<template>
  <AppLayout title="管理后台" description="这里将承载知识库管理、问答记录、数据大屏和游客感受度报告。" role-label="当前身份：管理员">
    <section class="workspace-grid">
      <article class="workspace-panel">
        <h2>RAG 知识库平台</h2>
        <p>配置景区、可复用知识库与正式导览 Profile，并上传资料进行向量化索引。</p>
        <el-button type="primary" :icon="Collection" @click="router.push('/admin/knowledge')">打开知识库平台</el-button>
      </article>
      <article class="workspace-panel">
        <h2>问答记录</h2>
        <p>后续展示游客问题、数字人回答、来源引用和情绪标签。</p>
      </article>

      <article class="workspace-panel">
        <h2>游客感受度报告</h2>
        <p>后续汇总热门问题、满意度趋势和服务优化建议。</p>
      </article>
    </section>
  </AppLayout>
</template>
