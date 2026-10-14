<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { X, ChevronDown, ChevronUp } from 'lucide-vue-next'
import { useQueue } from '../composables/useQueue'

const props = defineProps<{
  room: {
    id: number
    name: string
    assignment_id: number | null
    assignment_name: string | null
  }
  queueRoomId: number | null
  questions?: {
    id: number
    question_number: number
    label?: string | null
    description: string
    require_signoff?: boolean
  }[]
  rooms?: { id: number; name: string }[]
  isSignoff?: boolean
}>()

const emit = defineEmits<{ (e: 'close'): void }>()

const { submitRequest } = useQueue()
const router = useRouter()

const OTHER_SENTINEL = -1
const MIN_DESCRIPTION = 30
const MAX_FILE_SIZE = 10 * 1024 * 1024

function validateDescription(text: string): string | null {
  const trimmed = text.trim()
  if (trimmed.length < MIN_DESCRIPTION) {
    return `Please describe your problem (at least ${MIN_DESCRIPTION} characters).`
  }
  const frequencies: Record<string, number> = {}
  for (const ch of trimmed.toLowerCase()) frequencies[ch] = (frequencies[ch] ?? 0) + 1
  if (Math.max(...Object.values(frequencies)) / trimmed.length > 0.5) {
    return 'Please describe your problem meaningfully.'
  }
  return null
}

function validateCode(text: string): string | null {
  if (!text.trim()) return null
  const injectionPatterns = [/<script[\s>]/i, /javascript\s*:/i, /on\w{2,12}\s*=/i]
  if (injectionPatterns.some((pattern) => pattern.test(text))) {
    return 'Code contains disallowed content.'
  }
  return null
}

function validateFile(file: File): string | null {
  if (file.size > MAX_FILE_SIZE) {
    return `File too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Max 10 MB.`
  }
  if (!/\.(jpe?g|png|gif|webp|bmp|pdf)$/i.test(file.name)) {
    return 'Only images (jpg, png, gif, webp, bmp) and PDF are allowed.'
  }
  return null
}

const questionId = ref<number | null>(null)
const selectedRoomId = ref<number | null>(props.queueRoomId)
const studentComment = ref('')
const submissionText = ref('')
const screenshot = ref<File | null>(null)
const screenshotError = ref<string | null>(null)
const showExtra = ref(false)
const submitError = ref<string | null>(null)
const submitting = ref(false)
const descriptionError = ref<string | null>(null)
const codeError = ref<string | null>(null)

function handleClose() {
  emit('close')
}

function onDescriptionInput() {
  descriptionError.value = validateDescription(studentComment.value)
}

function onCodeInput() {
  codeError.value = validateCode(submissionText.value)
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0] ?? null
  screenshotError.value = null
  screenshot.value = null
  if (!file) return
  const validationError = validateFile(file)
  if (validationError) {
    screenshotError.value = validationError
    input.value = ''
    return
  }
  screenshot.value = file
}

async function handleSubmit() {
  if (questionId.value === null) {
    submitError.value = `Please select ${props.isSignoff ? 'an exercise' : 'a question'}.`
    return
  }
  if (!props.isSignoff) {
    const descriptionValidation = validateDescription(studentComment.value)
    if (descriptionValidation) {
      submitError.value = descriptionValidation
      return
    }
  }
  const codeValidation = validateCode(submissionText.value)
  if (codeValidation) {
    submitError.value = codeValidation
    return
  }

  submitError.value = null
  submitting.value = true
  const resolvedQuestionId = questionId.value === OTHER_SENTINEL ? null : questionId.value

  try {
    await submitRequest({
      question_id: resolvedQuestionId,
      submission_text: submissionText.value.trim(),
      student_comment: studentComment.value.trim(),
      queue_room_id: selectedRoomId.value,
      assignment_id: props.room.assignment_id,
      attachment: screenshot.value,
    })
    emit('close')
    if (props.room.assignment_id) {
      await router.push(`/student-queue/${props.room.assignment_id}`)
    }
  } catch (err: any) {
    const msg: string = err?.message ?? 'Something went wrong.'
    if (msg.toLowerCase().includes('already in a queue')) {
      submitError.value = 'You are already in a queue. Leave that queue before joining another.'
    } else {
      submitError.value = msg
    }
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" @mousedown.self="handleClose()">
      <div
        class="bg-white rounded-2xl shadow-2xl w-full max-w-lg flex flex-col overflow-hidden"
        style="max-height: 90vh"
      >
        <div class="flex items-start justify-between px-6 py-4 border-b border-gray-100 flex-shrink-0">
          <div class="min-w-0 pr-4">
            <h2 class="text-base font-semibold text-gray-900 truncate">Join Queue</h2>
            <p class="text-sm text-gray-500 mt-0.5 truncate">
              {{ room.assignment_name ?? room.name }}
            </p>
          </div>
          <button
            class="flex-shrink-0 text-gray-400 hover:text-gray-600 transition-colors mt-0.5"
            @click="handleClose()"
          >
            <X class="w-5 h-5" />
          </button>
        </div>

        <div class="flex-1 overflow-y-auto px-6 py-5 space-y-4">
          <div v-if="submitError" class="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
            {{ submitError }}
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">
              {{ isSignoff ? 'Exercise' : 'Question' }}
              <span class="text-red-500">*</span>
            </label>
            <select
              v-model="questionId"
              class="block w-full border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm px-3 py-2"
            >
              <option :value="null" disabled>Select {{ isSignoff ? 'an exercise' : 'a question' }}...</option>
              <option v-for="question in questions" :key="question.id" :value="question.id">
                {{ question.label ?? `Q${question.question_number}` }}:
                {{
                  question.description.length > 70 ? question.description.slice(0, 70) + '...' : question.description
                }}
              </option>
              <option v-if="!isSignoff" :value="OTHER_SENTINEL">Other</option>
            </select>
          </div>

          <div v-if="rooms && rooms.length > 1">
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Room</label>
            <select
              v-model="selectedRoomId"
              class="block w-full border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm px-3 py-2"
            >
              <option v-for="roomOption in rooms" :key="roomOption.id" :value="roomOption.id">
                {{ roomOption.name }}
              </option>
            </select>
          </div>

          <div v-if="!isSignoff">
            <label class="block text-sm font-medium text-gray-700 mb-1.5">
              Describe your problem
              <span class="text-red-500">*</span>
            </label>
            <textarea
              v-model="studentComment"
              rows="3"
              class="block w-full border rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm px-3 py-2 resize-y"
              :class="descriptionError && studentComment.length > 0 ? 'border-red-400' : 'border-gray-300'"
              placeholder="Describe what you're stuck on, what you've tried, and what the error says..."
              @input="onDescriptionInput"
            />
            <div class="flex items-center justify-between mt-1">
              <p v-if="descriptionError && studentComment.length > 0" class="text-xs text-red-600">
                {{ descriptionError }}
              </p>
              <span
                class="ml-auto text-xs tabular-nums"
                :class="studentComment.trim().length >= 30 ? 'text-emerald-600' : 'text-gray-400'"
              >
                {{ studentComment.trim().length }}
                <span class="text-gray-300">/ 30 min</span>
              </span>
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">
              {{ isSignoff ? 'Your Answer' : 'Your Code' }}
              <span class="text-gray-400 font-normal">(optional)</span>
            </label>
            <textarea
              v-model="submissionText"
              rows="4"
              class="block w-full border rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm font-mono px-3 py-2 resize-y"
              :class="codeError ? 'border-red-400' : 'border-gray-300'"
              placeholder="Paste your code here..."
              @input="onCodeInput"
            />
            <p v-if="codeError" class="mt-1 text-xs text-red-600">{{ codeError }}</p>
          </div>

          <div>
            <button
              type="button"
              class="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1 transition-colors"
              @click="showExtra = !showExtra"
            >
              Add a screenshot
              <ChevronDown v-if="!showExtra" class="w-4 h-4" />
              <ChevronUp v-else class="w-4 h-4" />
            </button>
            <div v-if="showExtra" class="mt-2">
              <input
                type="file"
                accept=".jpg,.jpeg,.png,.gif,.bmp,.webp,.pdf"
                class="block w-full text-sm text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                @change="onFileChange"
              />
              <p v-if="screenshotError" class="mt-1 text-xs text-red-600">{{ screenshotError }}</p>
              <p v-else-if="screenshot" class="mt-1 text-xs text-emerald-600">
                {{ screenshot.name }}
              </p>
              <p v-else class="mt-1 text-xs text-gray-400">JPG, PNG, GIF, BMP, WEBP or PDF - max 10 MB</p>
            </div>
          </div>
        </div>

        <div class="px-6 py-4 border-t border-gray-100 flex items-center justify-end gap-3 bg-gray-50 flex-shrink-0">
          <button
            class="px-4 py-2 text-sm font-medium rounded-lg text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 transition-colors"
            @click="emit('close')"
          >
            Cancel
          </button>
          <button
            :disabled="
              submitting || questionId === null || (!isSignoff && studentComment.trim().length < 30) || !!codeError
            "
            class="inline-flex items-center px-5 py-2 text-sm font-medium rounded-lg text-white bg-blue-600 hover:bg-blue-700 shadow-sm disabled:opacity-50 transition-colors"
            @click="handleSubmit"
          >
            {{ submitting ? 'Joining...' : 'Join Queue' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
