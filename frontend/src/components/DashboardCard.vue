<template>
  <Card :class="['dashboard-widget', cardClass]">
    <template v-if="$slots.title" #title>
      <slot name="title" />
    </template>
    <template v-if="$slots.subtitle" #subtitle>
      <slot name="subtitle" />
    </template>
    <template v-if="$slots.content" #content>
      <slot name="content" />
    </template>
    <!-- Fallback: if the caller uses the default slot for content, render it. -->
    <template v-if="!$slots.content && !$slots.title && !$slots.subtitle">
      <slot />
    </template>
  </Card>
</template>

<script setup>
import { computed } from 'vue'
import Card from 'primevue/card'

const props = defineProps({
  /** Additional classes to apply to the underlying PrimeVue Card. */
  cardClass: {
    type: String,
    default: '',
  },
})

// Keep a computed wrapper so the template doesn't accidentally treat the prop as reactive object.
const cardClass = computed(() => props.cardClass)
</script>

