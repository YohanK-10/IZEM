import { ref } from 'vue'
import { api } from '../api/client'

export interface Exercise {
  id: number
  question_number: number
  description: string
}

export function useQueue() {
  const exercises = ref<Exercise[]>([])
  const loadingExercises = ref(false)

  async function fetchExercises(assignmentId: number) {
    loadingExercises.value = true
    try {
      const res = await api.get<any>(`/queue/${assignmentId}`)
      exercises.value = (res.questions ?? []).map((q: any) => ({
        id: q.id,
        question_number: q.question_number,
        description: q.description ?? '',
      }))
    } finally {
      loadingExercises.value = false
    }
  }

  async function submitRequest(payload: {
    question_id: number | null
    submission_text: string
    student_comment: string
    queue_room_id: number | null
    assignment_id?: number | null
    attachment?: File | null
  }): Promise<{ request_id: number; queue_position: number }> {
    const form = new FormData()
    form.append('student_comment', payload.student_comment)
    form.append('submission_text', payload.submission_text)
    if (payload.question_id != null) form.append('question_id', String(payload.question_id))
    if (payload.queue_room_id != null) form.append('queue_room_id', String(payload.queue_room_id))
    if (payload.assignment_id != null) form.append('assignment_id', String(payload.assignment_id))
    if (payload.attachment) form.append('attachment', payload.attachment)
    return api.postForm('/student/help/submit', form)
  }

  async function pollStatus(requestId: number): Promise<{ status: string; final_feedback: string | null }> {
    return api.get(`/student/request/${requestId}/status`)
  }

  async function leaveQueue(): Promise<void> {
    await api.post('/queue/leave', {})
  }

  return { exercises, loadingExercises, fetchExercises, submitRequest, pollStatus, leaveQueue }
}
