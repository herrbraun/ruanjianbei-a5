<script setup lang="ts">
import AppLayout from '@/layouts/AppLayout.vue'
</script>

<template>
  <AppLayout title="管理后台" description="这里将承载知识库管理、问答记录、数据大屏和游客感受度报告。" role-label="当前身份：管理员">
    <section class="workspace-grid">
      <article class="workspace-panel">
        <h2>知识库管理</h2>
        <p>后续支持上传景区资料、解析文档、切分文本并写入向量库。</p>
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
