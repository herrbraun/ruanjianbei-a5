<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps<{
  option: Record<string, unknown>
  empty?: boolean
  emptyText?: string
  summary: string
}>()

const chartRoot = ref<HTMLElement | null>(null)
let chart: { setOption: (option: Record<string, unknown>, notMerge?: boolean) => void; resize: () => void; dispose: () => void } | null = null
let resizeObserver: ResizeObserver | null = null

async function renderChart() {
  if (props.empty) return
  await nextTick()
  if (!chartRoot.value) return
  const { init } = await import('@/services/chartRuntime')
  chart ||= init(chartRoot.value)
  chart.setOption(props.option, true)
  resizeObserver ||= new ResizeObserver(() => chart?.resize())
  resizeObserver.observe(chartRoot.value)
}

watch(() => props.option, renderChart, { deep: true })
watch(() => props.empty, (empty) => {
  if (empty) {
    resizeObserver?.disconnect()
    chart?.dispose()
    chart = null
    return
  }
  renderChart()
})
onMounted(renderChart)
onBeforeUnmount(() => { resizeObserver?.disconnect(); chart?.dispose() })
</script>

<template>
  <div v-if="empty" class="chart-empty"><span>{{ emptyText || '暂无内容' }}</span></div>
  <div v-else ref="chartRoot" class="insight-chart" role="img" :aria-label="summary" />
</template>
