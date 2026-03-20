<template>
  <span class="dashboard-keyword-tag">{{ text }}</span>
</template>

<script setup>
defineProps({
  text: {
    type: String,
    default: '',
  },
})
</script>

