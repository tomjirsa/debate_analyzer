<template>
  <div class="stat-bar-chart">
    <v-chart
      class="chart"
      :option="chartOption"
      :autoresize="true"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  TitleComponent,
} from 'echarts/components'
import { chartTheme } from '../theme/chart-theme'

use([
  CanvasRenderer,
  BarChart,
  GridComponent,
  TooltipComponent,
  TitleComponent,
])

// PrimeVue dark mode toggles by adding/removing `.app-dark` on `documentElement`.
// ECharts option values are built from CSS variables at compute time, so we
// trigger recomputation when the theme class changes.
const themeVersion = ref(0)

let classObserver = null

onMounted(() => {
  classObserver = new MutationObserver(() => {
    themeVersion.value += 1
  })
  classObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
})

onBeforeUnmount(() => {
  classObserver && classObserver.disconnect()
  classObserver = null
})

const props = defineProps({
  /** X-axis labels (e.g. transcript titles). */
  labels: {
    type: Array,
    default: () => [],
  },
  /** Y-axis values (same length as labels). */
  values: {
    type: Array,
    default: () => [],
  },
  /** Chart title (optional). */
  title: {
    type: String,
    default: '',
  },
  /** Y-axis name (e.g. "Share (%)" or "Time (min)"). */
  yAxisName: {
    type: String,
    default: '',
  },
  /** Format value for tooltip display. Receives (value) and returns string. */
  valueFormatter: {
    type: Function,
    default: (v) => String(v),
  },
})

const chartOption = computed(() => {
  // Ensure ECharts option updates when the theme toggles.
  void themeVersion.value
  const { labels, values, title, yAxisName, valueFormatter } = props
  const { primaryColor, gridColor, textColor, tooltipBg } = chartTheme
  return {
    title: title ? { text: title, left: 'center', textStyle: { color: textColor } } : undefined,
    tooltip: {
      trigger: 'axis',
      backgroundColor: tooltipBg,
      borderColor: gridColor,
      borderWidth: 1,
      textStyle: { color: textColor },
      axisPointer: { type: 'shadow' },
      formatter: (items) => {
        if (!items || !items.length) return ''
        const item = items[0]
        const idx = item.dataIndex
        const label = labels[idx]
        const value = values[idx]
        const formatted = valueFormatter(value)
        return `${label}<br/>${formatted}`
      },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '10%',
      top: title ? 40 : 20,
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisLabel: {
        rotate: 45,
        width: 120,
        overflow: 'truncate',
        interval: 0,
        color: textColor,
      },
      axisLine: { lineStyle: { color: gridColor } },
      axisTick: { show: false },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      name: yAxisName,
      nameGap: 40,
      nameTextStyle: { color: textColor },
      axisLabel: { color: textColor },
      axisLine: { show: false },
      splitLine: { lineStyle: { color: gridColor, type: 'dashed' } },
    },
    series: [
      {
        name: yAxisName,
        type: 'bar',
        data: values,
        itemStyle: {
          color: primaryColor,
          borderRadius: [6, 6, 0, 0],
        },
        emphasis: {
          itemStyle: {
            borderRadius: [6, 6, 0, 0],
          },
        },
      },
    ],
  }
})
</script>

<style scoped>
.stat-bar-chart {
  width: 100%;
  max-height: 280px;
  min-height: 200px;
}
.chart {
  width: 100%;
  height: 100%;
  min-height: 200px;
}
</style>
