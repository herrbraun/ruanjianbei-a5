<script setup lang="ts">
import { ArrowRight, Lock, Location, RefreshRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { knowledgeApi, type ScenicArea } from '@/api/knowledge'
import { useAuthStore } from '@/stores/auth'
import { useScenicStore } from '@/stores/scenic'

const router = useRouter()
const authStore = useAuthStore()
const scenicStore = useScenicStore()
const scenicAreas = ref<ScenicArea[]>([])
const selectedCode = ref('')
const loading = ref(false)
const starting = ref(false)
const loadFailed = ref(false)

const selectedArea = computed(() => scenicAreas.value.find((area) => area.code === selectedCode.value))

async function loadScenicAreas() {
  loading.value = true
  loadFailed.value = false
  try {
    scenicAreas.value = (await knowledgeApi.listPublicScenicAreas()).data.filter((area) => area.is_enabled)
    const storedCode = scenicStore.selectedCode
    selectedCode.value = scenicAreas.value.some((area) => area.code === storedCode)
      ? storedCode
      : scenicAreas.value[0]?.code || ''
  } catch {
    loadFailed.value = true
  } finally {
    loading.value = false
  }
}

async function startGuide() {
  if (starting.value || !selectedArea.value) return
  starting.value = true
  try {
    if (authStore.user?.role === 'admin') authStore.logout(true)
    await authStore.ensureGuestSession()
    scenicStore.select(selectedArea.value)
    await router.push({ path: '/visitor/guide', query: { scenic_code: selectedArea.value.code, start: '1' } })
  } catch {
    ElMessage.error('暂时无法开始导览，请检查网络后重试')
  } finally {
    starting.value = false
  }
}

onMounted(loadScenicAreas)
</script>

<template>
  <main class="landing-page">
    <div class="landing-grain" aria-hidden="true" />
    <header class="landing-header">
      <a class="landing-brand" href="#main"><span>灵</span><div><strong>灵境智游</strong><small>DIGITAL SCENIC GUIDE</small></div></a>
      <RouterLink class="admin-entrance" to="/admin/login" aria-label="管理员入口" title="管理员入口"><el-icon><Lock /></el-icon><span>管理员入口</span></RouterLink>
    </header>

    <section id="main" class="landing-hero">
      <div class="hero-copy">
        <p class="hero-kicker"><i /> 山水有声 · 智游无界</p>
        <h1>选一处风景，<br><em>让讲解随你出发。</em></h1>
        <p class="hero-description">无需注册与登录。选择你要游览的景区，数字讲解员将为你介绍景点故事、规划路线，并随时回答问题。</p>
        <div class="hero-notes"><span>语音问答</span><span>个性路线</span><span>数字人讲解</span></div>
      </div>

      <section class="scenic-selector" aria-label="选择景区">
        <div class="selector-number">01</div>
        <div class="selector-heading"><span>SCENIC DESTINATION</span><h2>今天，想从哪里开始？</h2></div>

        <div v-if="loading" class="selector-loading"><el-skeleton animated :rows="4" /></div>
        <div v-else-if="loadFailed" class="selector-error">
          <el-icon><RefreshRight /></el-icon><strong>景区列表加载失败</strong><p>请确认网络连接后重新尝试。</p><el-button @click="loadScenicAreas">重新加载</el-button>
        </div>
        <div v-else-if="!scenicAreas.length" class="selector-error"><el-icon><Location /></el-icon><strong>暂无开放景区</strong><p>管理员上架景区后即可开始导览。</p></div>
        <template v-else>
          <el-select v-model="selectedCode" class="landing-select" size="large" placeholder="请选择景区" :disabled="starting">
            <el-option v-for="area in scenicAreas" :key="area.code" :label="area.name" :value="area.code" />
          </el-select>
          <article v-if="selectedArea" class="selected-scenic-card">
            <span class="scenic-mark">{{ selectedArea.name.slice(0, 1) }}</span>
            <div><small>当前目的地</small><strong>{{ selectedArea.name }}</strong><p>{{ selectedArea.description || '景区数字导览服务已准备就绪' }}</p></div>
          </article>
          <el-button class="landing-start" type="primary" size="large" :loading="starting" :disabled="!selectedCode" @click="startGuide">
            开始数字人导览 <el-icon><ArrowRight /></el-icon>
          </el-button>
          <p class="privacy-note">继续即创建匿名游览身份，仅用于保存本机导览进度与偏好。</p>
        </template>
      </section>
    </section>

    <footer class="landing-footer"><span>AI 数字人景区导览系统</span><span>灵山文化 · 智慧文旅</span></footer>
  </main>
</template>

<style scoped>
.landing-page{--ink:#123f3a;--jade:#0b7468;--paper:#f5f2e9;--gold:#b88a38;position:relative;min-height:100vh;overflow:hidden;color:var(--ink);background:radial-gradient(circle at 75% 18%,rgba(212,227,207,.82),transparent 28%),linear-gradient(135deg,#f8f6ef 0%,#edf3e9 56%,#e5eee7 100%);font-family:"Noto Serif SC","Songti SC",serif}.landing-page:before{content:"山";position:absolute;left:-4vw;bottom:-18vh;font-size:min(70vw,760px);line-height:1;color:rgba(31,94,80,.035);font-family:"STKaiti","KaiTi",serif;pointer-events:none}.landing-grain{position:absolute;inset:0;opacity:.18;pointer-events:none;background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 180 180' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.12'/%3E%3C/svg%3E")}.landing-header,.landing-hero,.landing-footer{position:relative;z-index:1}.landing-header{height:92px;padding:0 clamp(24px,6vw,92px);display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid rgba(18,63,58,.12)}.landing-brand{display:flex;align-items:center;gap:12px;color:inherit;text-decoration:none}.landing-brand>span{display:grid;place-items:center;width:42px;height:42px;border:1px solid var(--gold);border-radius:50%;font-size:21px;color:var(--jade)}.landing-brand div{display:flex;flex-direction:column}.landing-brand strong{font-size:19px;letter-spacing:.15em}.landing-brand small{margin-top:3px;font:9px/1.2 Georgia,serif;letter-spacing:.2em;color:#64807a}.admin-entrance{display:flex;align-items:center;gap:7px;padding:9px 13px;border:1px solid rgba(18,63,58,.16);border-radius:999px;color:#476b64;text-decoration:none;font:13px/1 "Microsoft YaHei",sans-serif;transition:.2s}.admin-entrance:hover{border-color:var(--jade);color:var(--jade);background:rgba(255,255,255,.55)}.landing-hero{min-height:calc(100vh - 150px);max-width:1280px;margin:auto;padding:clamp(48px,8vh,100px) clamp(24px,6vw,74px);display:grid;grid-template-columns:minmax(0,1.08fr) minmax(360px,.72fr);gap:clamp(48px,8vw,120px);align-items:center}.hero-copy{animation:rise .7s ease both}.hero-kicker{display:flex;align-items:center;gap:10px;margin:0 0 26px;font:600 12px/1 "Microsoft YaHei",sans-serif;letter-spacing:.28em;color:var(--jade)}.hero-kicker i{width:30px;height:1px;background:var(--gold)}.hero-copy h1{margin:0;font-size:clamp(48px,6.2vw,88px);font-weight:500;line-height:1.14;letter-spacing:-.04em}.hero-copy h1 em{font-style:normal;color:var(--jade)}.hero-description{max-width:580px;margin:32px 0 24px;font:16px/1.9 "Microsoft YaHei",sans-serif;color:#58706b}.hero-notes{display:flex;flex-wrap:wrap;gap:8px}.hero-notes span{padding:7px 13px;border-radius:999px;background:rgba(255,255,255,.55);font:12px/1 "Microsoft YaHei",sans-serif;color:#55716b}.scenic-selector{position:relative;padding:38px;border:1px solid rgba(18,63,58,.17);border-radius:4px 40px 4px 4px;background:rgba(253,252,247,.78);box-shadow:0 28px 80px rgba(29,74,64,.12);backdrop-filter:blur(16px);animation:rise .7s .12s ease both}.selector-number{position:absolute;right:28px;top:18px;font:italic 52px/1 Georgia,serif;color:rgba(184,138,56,.17)}.selector-heading span{font:10px/1 Georgia,serif;letter-spacing:.23em;color:var(--gold)}.selector-heading h2{margin:10px 0 28px;font-size:27px;font-weight:600}.landing-select{width:100%}.selected-scenic-card{display:flex;gap:16px;margin:18px 0;padding:20px;border-left:2px solid var(--gold);background:#edf4ee}.scenic-mark{flex:0 0 48px;height:48px;display:grid;place-items:center;border-radius:50%;background:var(--jade);color:white;font-size:22px}.selected-scenic-card div{min-width:0;display:flex;flex-direction:column}.selected-scenic-card small{font:11px/1 "Microsoft YaHei",sans-serif;color:#78908b}.selected-scenic-card strong{margin:5px 0;font-size:19px}.selected-scenic-card p{margin:0;display:-webkit-box;overflow:hidden;-webkit-line-clamp:2;-webkit-box-orient:vertical;font:12px/1.6 "Microsoft YaHei",sans-serif;color:#637c76}.landing-start{width:100%;height:52px!important;border-radius:2px!important;background:var(--jade)!important;border-color:var(--jade)!important;font-weight:600;letter-spacing:.08em}.landing-start .el-icon{margin-left:8px}.privacy-note{margin:13px 0 0;text-align:center;font:11px/1.5 "Microsoft YaHei",sans-serif;color:#82958f}.selector-loading{min-height:250px}.selector-error{min-height:240px;display:flex;align-items:center;justify-content:center;flex-direction:column;text-align:center;color:#6a827c}.selector-error .el-icon{font-size:32px;color:var(--gold)}.selector-error strong{margin-top:14px}.selector-error p{font:13px/1.6 "Microsoft YaHei",sans-serif}.landing-footer{height:58px;padding:0 clamp(24px,6vw,92px);display:flex;align-items:center;justify-content:space-between;border-top:1px solid rgba(18,63,58,.1);font:10px/1 Georgia,"Microsoft YaHei",sans-serif;letter-spacing:.14em;color:#718680}@keyframes rise{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:none}}@media(max-width:820px){.landing-header{height:70px;padding:0 18px}.landing-brand>span{width:36px;height:36px}.landing-brand strong{font-size:16px}.landing-brand small{display:none}.admin-entrance span{display:none}.admin-entrance{width:38px;height:38px;padding:0;justify-content:center}.landing-hero{min-height:auto;padding:40px 18px 54px;grid-template-columns:1fr;gap:34px}.hero-copy h1{font-size:clamp(42px,12vw,62px)}.hero-description{margin:22px 0;font-size:14px}.scenic-selector{padding:28px 22px;border-radius:3px 30px 3px 3px}.selector-heading h2{font-size:23px}.landing-footer{height:48px;padding:0 18px}.landing-footer span:last-child{display:none}}@media(prefers-reduced-motion:reduce){.hero-copy,.scenic-selector{animation:none}}
</style>
