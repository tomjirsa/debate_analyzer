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
import { computed } from 'vue'
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
  const { labels, values, title, yAxisName, valueFormatter } = props
  const { primaryColor, gridColor, textColor, tooltipBg } = chartTheme
  return {
    title: title ? { text: title, left: 'center', textStyle: { color: textColor } } : undefined,
    tooltip: {
      trigger: 'axis',
      backgroundColor: tooltipBg,
      borderColor: gridColor,
      textStyle: { color: textColor },
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
