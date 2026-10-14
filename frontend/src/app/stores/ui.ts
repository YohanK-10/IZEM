import { defineStore } from 'pinia'
import { ref } from 'vue'

type DialogKind = 'confirm' | 'alert'
type DialogTone = 'default' | 'danger'

export interface DialogState {
  kind: DialogKind
  tone: DialogTone
  title: string
  message: string
  confirmLabel: string
  cancelLabel: string | null
}

export const useUIStore = defineStore('ui', () => {
  const activeCourseId = ref<number | null>(null)
  const dialog = ref<DialogState | null>(null)
  let dialogResolver: ((value: boolean) => void) | null = null

  function setActiveCourse(id: number | null) {
    activeCourseId.value = id
  }

  function openDialog(state: DialogState): Promise<boolean> {
    if (dialogResolver) {
      dialogResolver(false)
    }

    dialog.value = state

    return new Promise((resolve) => {
      dialogResolver = resolve
    })
  }

  function confirm(options: {
    title: string
    message: string
    confirmLabel?: string
    cancelLabel?: string
    tone?: DialogTone
  }) {
    return openDialog({
      kind: 'confirm',
      tone: options.tone ?? 'default',
      title: options.title,
      message: options.message,
      confirmLabel: options.confirmLabel ?? 'Continue',
      cancelLabel: options.cancelLabel ?? 'Cancel',
    })
  }

  async function alert(options: { title: string; message: string; confirmLabel?: string; tone?: DialogTone }) {
    await openDialog({
      kind: 'alert',
      tone: options.tone ?? 'default',
      title: options.title,
      message: options.message,
      confirmLabel: options.confirmLabel ?? 'OK',
      cancelLabel: null,
    })
  }

  function resolveDialog(confirmed: boolean) {
    const isAlert = dialog.value?.kind === 'alert'
    const resolver = dialogResolver

    dialog.value = null
    dialogResolver = null
    resolver?.(isAlert ? true : confirmed)
  }

  function acceptDialog() {
    resolveDialog(true)
  }

  function dismissDialog() {
    resolveDialog(false)
  }

  return {
    activeCourseId,
    dialog,
    setActiveCourse,
    confirm,
    alert,
    acceptDialog,
    dismissDialog,
  }
})
