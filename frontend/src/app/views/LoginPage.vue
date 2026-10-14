<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { Send } from 'lucide-vue-next'
import IZEMLogo from '../components/IZEMLogo.vue'

const router = useRouter()
const authStore = useAuthStore()

const email = ref('')
const submitting = ref(false)
const error = ref<string | null>(null)
const successMessage = ref<string | null>(null)

async function handleSubmit() {
  if (!email.value.trim()) {
    error.value = 'Please enter your email address'
    return
  }
  submitting.value = true
  error.value = null
  successMessage.value = null
  try {
    const result = await authStore.login(email.value.trim())
    if ('user' in result) {
      const target =
        result.user.role === 'student' ? '/student-home' : result.user.role === 'ta' ? '/ta-dashboard' : '/'
      router.push(target)
    } else {
      successMessage.value = (result as { message: string }).message
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Login failed. Please try again.'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-gray-50 flex items-center justify-center p-4">
    <div class="max-w-sm w-full">
      <div class="text-center mb-8">
        <div class="flex items-center justify-center mb-4">
          <IZEMLogo :size="56" />
        </div>
        <h1 class="text-2xl font-bold text-gray-900">IZEM</h1>
        <p class="mt-1 text-sm text-gray-500">Sign in with your email</p>
      </div>

      <div v-if="error" class="mb-4 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
        {{ error }}
      </div>
      <div
        v-if="successMessage"
        class="mb-4 bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-sm text-blue-700"
      >
        {{ successMessage }}
      </div>

      <div class="bg-white shadow rounded-lg p-6">
        <form class="space-y-4" @submit.prevent="handleSubmit">
          <div>
            <label for="email" class="block text-sm font-medium text-gray-700 mb-1">Email address</label>
            <input
              id="email"
              v-model="email"
              type="email"
              required
              placeholder="you@example.com"
              :disabled="submitting"
              class="block w-full border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm px-3 py-2.5 disabled:bg-gray-50"
            />
          </div>
          <button
            type="submit"
            :disabled="submitting"
            class="w-full inline-flex justify-center items-center px-4 py-2.5 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:bg-blue-400"
          >
            <Send class="mr-2 w-4 h-4" />
            {{ submitting ? 'Signing in…' : 'Send Magic Link' }}
          </button>
        </form>
      </div>

      <p class="mt-6 text-center text-xs text-gray-400">
        Test:
        <button type="button" class="text-blue-500 hover:underline" @click="email = 'teacher@example.com'">
          teacher@example.com
        </button>
        &middot;
        <button type="button" class="text-blue-500 hover:underline" @click="email = 'student@example.com'">
          student@example.com
        </button>
        &middot;
        <button type="button" class="text-blue-500 hover:underline" @click="email = 'ta@example.com'">
          ta@example.com
        </button>
      </p>
    </div>
  </div>
</template>
