<script setup lang="ts">
interface Props { size?: number }
withDefaults(defineProps<Props>(), { size: 40 })
</script>

<template>
  <svg :width="size" :height="size" viewBox="0 0 48 48" fill="none" aria-label="IZEM">
    <rect x="4" y="4" width="40" height="40" rx="12" fill="#2563EB" />
    <path d="M14 16H34M14 24H29M14 32H24" stroke="white" stroke-width="4" stroke-linecap="round" />
  </svg>
</template>
