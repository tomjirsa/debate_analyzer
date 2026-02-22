<template>
  <div class="share-gauge">
    <v-chart
      class="gauge-chart"
      :option="gaugeOption"
      :autoresize="true"
    />
    <span class="gauge-label">{{ label }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { GaugeChart } from 'echarts/charts'
import { TitleComponent } from 'echarts/components'

use([CanvasRenderer, GaugeChart, TitleComponent])

const props = defineProps({
  /** Share value 0–1 (e.g. 0.25 = 25%). */
  value: {
    type: Number,
    default: 0,
  },
  /** Label below the gauge (e.g. "Share of speaking time"). */
  label: {
    type: String,
    default: '',
  },
})

const gaugeOption = computed(() => {
  const pct = Math.min(100, Math.max(0, (Number(props.value) || 0) * 100))
  return {
    series: [
      {
        type: 'gauge',
        min: 0,
        max: 100,
        startAngle: 180,
        endAngle: 0,
        radius: '85%',
        center: ['50%', '75%'],
        progress: {
          show: true,
          width: 12,
          roundCap: true,
        },
        pointer: {
          show: false,
        },
        axisLine: {
          lineStyle: { width: 12 },
        },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        anchor: { show: false },
        title: { show: false },
        detail: {
          valueAnimation: true,
          offsetCenter: [0, '-15%'],
          fontSize: 18,
          fontWeight: 600,
          formatter: '{value}%',
        },
        data: [{ value: Math.round(pct * 10) / 10 }],
      },
    ],
  }
})
</script>

<style scoped>
.share-gauge {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 100px;
}
.gauge-chart {
  width: 100%;
  height: 80px;
  min-height: 80px;
}
.gauge-label {
  font-size: 0.75rem;
  color: #666;
  text-align: center;
  margin-top: 0.25rem;
  max-width: 120px;
}
</style>
