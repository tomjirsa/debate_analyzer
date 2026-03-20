<template>
  <div class="dashboard-chart-section">
    <div class="dashboard-chart-header">
      <slot name="controls" />
    </div>
    <slot />
  </div>
</template>

<script setup>
// Structural wrapper only; styling is handled via shared `.dashboard-*` classes.
</script>

<style scoped>
:deep(.chart-label) {
  font-size: 0.9rem;
}

:deep(.chart-select) {
  min-width: 200px;
}
</style>

