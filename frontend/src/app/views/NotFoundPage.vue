<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { Home, MapPinOff } from 'lucide-vue-next'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()

const homePath = computed(() => {
  if (authStore.isTA) return '/ta-dashboard'
  if (authStore.isStudent) return '/student-home'
  return '/'
})
</script>

<template>
  <div
    class="mx-auto flex max-w-2xl flex-col items-center justify-center rounded-3xl border border-gray-200 bg-white px-6 py-20 text-center shadow-sm"
  >
    <div class="mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-blue-100 text-blue-600">
      <MapPinOff class="h-8 w-8" />
    </div>
    <p class="text-sm font-semibold uppercase tracking-[0.22em] text-blue-600">404</p>
    <h1 class="mt-3 text-3xl font-bold tracking-tight text-gray-900">Page not found</h1>
    <p class="mt-4 max-w-lg text-sm leading-6 text-gray-600">
      This route does not exist in IZEM, or the page has moved. Use the button below to get back to a valid screen.
    </p>
    <RouterLink
      :to="homePath"
      class="mt-8 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700"
    >
      <Home class="h-4 w-4" />
      Go to Home
    </RouterLink>
  </div>
</template>
