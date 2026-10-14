<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Eye } from 'lucide-vue-next'

const router = useRouter()
const roomId = ref('')
const error = ref('')
const busy = ref(false)

async function goToRoom() {
  const id = roomId.value.trim()
  if (!id) return
  error.value = ''
  busy.value = true
  try {
    const res = await fetch(`/view/room/${encodeURIComponent(id)}/status`)
    if (res.ok) {
      router.push({ name: 'viewer-room', params: { roomId: id } })
    } else {
      error.value = 'Room not found. Please check the ID and try again.'
    }
  } catch {
    error.value = 'Could not reach the server. Please try again.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-gray-50 flex items-center justify-center p-4">
    <div class="w-full max-w-md">
      <div class="text-center mb-8">
        <div class="w-16 h-16 rounded-2xl bg-blue-100 flex items-center justify-center mx-auto mb-4">
          <Eye class="w-8 h-8 text-blue-600" />
        </div>
        <h1 class="text-3xl font-bold text-gray-900">View-Only Queue</h1>
        <p class="mt-2 text-gray-500">Enter a room ID to see who is queued and who is being helped.</p>
      </div>

      <div class="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
        <form class="space-y-4" @submit.prevent="goToRoom">
          <div>
            <label for="room-id" class="block text-sm font-medium text-gray-700 mb-1.5">Room ID</label>
            <div class="flex gap-3">
              <input
                id="room-id"
                v-model="roomId"
                type="number"
                min="1"
                required
                placeholder="e.g. 1"
                class="flex-1 border border-gray-300 rounded-lg px-4 py-3 text-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                autofocus
              />
              <button
                type="submit"
                :disabled="busy || !roomId.trim()"
                class="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg disabled:opacity-50 transition-colors"
              >
                {{ busy ? '…' : 'View' }}
              </button>
            </div>
          </div>

          <div v-if="error" class="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
            {{ error }}
          </div>
        </form>
      </div>

      <p class="mt-6 text-center text-sm text-gray-400">No login required. Ask your TA or teacher for the room ID.</p>
    </div>
  </div>
</template>
