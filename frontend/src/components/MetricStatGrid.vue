<template>
  <div class="dashboard-stat-grid">
    <MetricStatCard
      v-for="item in items"
      :key="item.key"
      :value="item.value"
      :label="item.label"
    />
  </div>
</template>

<script setup>
import MetricStatCard from './MetricStatCard.vue'

defineProps({
  /**
   * Array of { key, value, label } objects.
   * `key` is used for v-for identity.
   */
  items: {
    type: Array,
    default: () => [],
  },
})
</script>

