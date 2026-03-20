<template>
  <div class="dashboard-stat-tile">
    <span class="value">{{ value }}</span>
    <br />
    <span class="label">{{ label }}</span>
  </div>
</template>

<script setup>
const props = defineProps({
  value: {
    type: [String, Number],
    default: '—',
  },
  label: {
    type: String,
    default: '',
  },
})

// Vue templates can access props directly when using <script setup>.
const value = props.value
const label = props.label
</script>

