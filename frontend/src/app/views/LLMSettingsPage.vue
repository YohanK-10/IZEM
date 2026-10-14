<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { llmApi } from '../api'
import type { LLMConfig, LLMConfigsResponse } from '../types'
import { useUIStore } from '../stores/ui'

const data = ref<LLMConfigsResponse | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const uiStore = useUIStore()

// Form state
const showForm = ref(false)
const editingId = ref<number | null>(null)
const form = ref({ name: '', base_url: '', api_key: '', model_name: '', is_public: false })
const saving = ref(false)
const saveError = ref<string | null>(null)

// Test connection
const testResult = ref<{ id: number; ok: boolean; message?: string } | null>(null)
const testing = ref<number | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    data.value = await llmApi.list()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load LLM configs'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.value = { name: '', base_url: '', api_key: '', model_name: '', is_public: false }
  saveError.value = null
  showForm.value = true
}

function openEdit(llm: LLMConfig) {
  editingId.value = llm.id
  form.value = {
    name: llm.name,
    base_url: llm.base_url,
    api_key: '',
    model_name: llm.model_name,
    is_public: llm.is_public,
  }
  saveError.value = null
  showForm.value = true
}

function cancelForm() {
  showForm.value = false
  editingId.value = null
}

async function save() {
  saving.value = true
  saveError.value = null
  try {
    if (editingId.value !== null) {
      await llmApi.update(editingId.value, form.value)
    } else {
      await llmApi.create(form.value)
    }
    showForm.value = false
    await load()
  } catch (err) {
    saveError.value = err instanceof Error ? err.message : 'Failed to save'
  } finally {
    saving.value = false
  }
}

async function remove(llm: LLMConfig) {
  const confirmed = await uiStore.confirm({
    title: 'Delete LLM configuration',
    message: `Delete "${llm.name}"? Assignments and sessions using it will be unlinked.`,
    confirmLabel: 'Delete LLM',
    tone: 'danger',
  })
  if (!confirmed) return

  try {
    await llmApi.delete(llm.id)
    await load()
  } catch (err) {
    await uiStore.alert({
      title: 'LLM could not be deleted',
      message: err instanceof Error ? err.message : 'Delete failed',
      tone: 'danger',
    })
  }
}

async function testConnection(llm: LLMConfig) {
  testing.value = llm.id
  testResult.value = null
  try {
    const res = await llmApi.testSaved(llm.id)
    testResult.value = { id: llm.id, ok: res.ok, message: res.message }
  } catch (err) {
    testResult.value = {
      id: llm.id,
      ok: false,
      message: err instanceof Error ? err.message : 'Connection failed',
    }
  } finally {
    testing.value = null
  }
}

onMounted(load)
</script>

<template>
  <div class="p-4 sm:p-6 lg:p-8">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-900">AI / LLM Settings</h1>
      <button
        class="bg-blue-600 hover:bg-blue-700 text-white text-sm px-4 py-2 rounded transition-colors"
        @click="openCreate"
      >
        + Add LLM
      </button>
    </div>

    <div v-if="loading" class="text-gray-500 text-sm">Loading…</div>
    <div v-else-if="error" class="bg-red-50 border border-red-200 text-red-800 p-4 rounded text-sm">
      {{ error }}
    </div>

    <template v-else-if="data">
      <!-- Add / Edit form -->
      <div v-if="showForm" class="bg-white border border-gray-200 rounded-lg p-6 mb-6">
        <h2 class="text-base font-semibold text-gray-900 mb-4">
          {{ editingId ? 'Edit LLM config' : 'Add LLM config' }}
        </h2>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm text-gray-700 mb-1">Name</label>
            <input
              v-model="form.name"
              type="text"
              class="w-full border border-gray-300 rounded px-3 py-2 text-sm"
              placeholder="My LLM"
            />
          </div>
          <div>
            <label class="block text-sm text-gray-700 mb-1">Model name</label>
            <input
              v-model="form.model_name"
              type="text"
              class="w-full border border-gray-300 rounded px-3 py-2 text-sm"
              placeholder="gpt-4o"
            />
          </div>
          <div class="sm:col-span-2">
            <label class="block text-sm text-gray-700 mb-1">Base URL</label>
            <input
              v-model="form.base_url"
              type="text"
              class="w-full border border-gray-300 rounded px-3 py-2 text-sm"
              placeholder="https://api.openai.com/v1"
            />
          </div>
          <div class="sm:col-span-2">
            <label class="block text-sm text-gray-700 mb-1">
              API key{{ editingId ? ' (leave blank to keep existing)' : '' }}
            </label>
            <input
              v-model="form.api_key"
              type="password"
              class="w-full border border-gray-300 rounded px-3 py-2 text-sm"
              placeholder="sk-…"
            />
          </div>
          <div class="sm:col-span-2 flex items-center gap-2">
            <input id="is_public" v-model="form.is_public" type="checkbox" class="rounded" />
            <label for="is_public" class="text-sm text-gray-700">Make this config available to all TAs</label>
          </div>
        </div>

        <div v-if="saveError" class="mt-3 bg-red-50 border border-red-200 text-red-800 text-sm px-3 py-2 rounded">
          {{ saveError }}
        </div>

        <div class="flex gap-2 mt-4">
          <button
            :disabled="saving"
            class="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white text-sm px-4 py-2 rounded transition-colors"
            @click="save"
          >
            {{ saving ? 'Saving…' : 'Save' }}
          </button>
          <button
            class="border border-gray-300 text-gray-700 hover:bg-gray-50 text-sm px-4 py-2 rounded"
            @click="cancelForm"
          >
            Cancel
          </button>
        </div>
      </div>

      <!-- My configs -->
      <section class="mb-8">
        <h2 class="text-base font-semibold text-gray-900 mb-3">My configurations</h2>
        <div v-if="data.my_configs.length === 0" class="text-sm text-gray-500">
          No LLM configurations yet. Click "+ Add LLM" to create one.
        </div>
        <div v-else class="space-y-3">
          <div
            v-for="llm in data.my_configs"
            :key="llm.id"
            class="bg-white border border-gray-200 rounded-lg p-4 flex items-center gap-4"
          >
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="font-medium text-gray-900">{{ llm.name }}</span>
                <span class="text-xs text-gray-500">{{ llm.model_name }}</span>
                <span v-if="llm.is_public" class="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">Public</span>
              </div>
              <div class="text-xs text-gray-400 mt-0.5 truncate">{{ llm.base_url }}</div>

              <!-- Test result -->
              <div v-if="testResult?.id === llm.id" class="mt-1">
                <span v-if="testResult.ok" class="text-xs text-green-600">✓ Connection OK</span>
                <span v-else class="text-xs text-red-600">✗ {{ testResult.message ?? 'Connection failed' }}</span>
              </div>
            </div>

            <div class="flex gap-2 flex-shrink-0">
              <button
                :disabled="testing === llm.id"
                class="text-xs border border-gray-300 text-gray-600 hover:bg-gray-50 px-2 py-1 rounded"
                @click="testConnection(llm)"
              >
                {{ testing === llm.id ? 'Testing…' : 'Test' }}
              </button>
              <button
                class="text-xs border border-gray-300 text-gray-600 hover:bg-gray-50 px-2 py-1 rounded"
                @click="openEdit(llm)"
              >
                Edit
              </button>
              <button
                class="text-xs border border-red-200 text-red-600 hover:bg-red-50 px-2 py-1 rounded"
                @click="remove(llm)"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- Public configs -->
      <section v-if="data.public_configs.length > 0">
        <h2 class="text-base font-semibold text-gray-900 mb-3">Public configurations (shared by others)</h2>
        <div class="space-y-3">
          <div
            v-for="llm in data.public_configs"
            :key="llm.id"
            class="bg-gray-50 border border-gray-200 rounded-lg p-4 flex items-center gap-4"
          >
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <span class="font-medium text-gray-900">{{ llm.name }}</span>
                <span class="text-xs text-gray-500">{{ llm.model_name }}</span>
              </div>
              <div class="text-xs text-gray-400 mt-0.5 truncate">{{ llm.base_url }}</div>
            </div>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>
