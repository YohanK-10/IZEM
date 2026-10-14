import { describe, it, expect, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useUIStore } from '@/app/stores/ui'
import AppDialog from '@/app/components/AppDialog.vue'

// AppDialog uses <Teleport to="body"> so content renders directly in document.body,
// not inside wrapper.element. We check document.body.textContent instead.

describe('AppDialog', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders nothing when no dialog is open', () => {
    mount(AppDialog, { attachTo: document.body })
    expect(document.body.querySelector('[class*="fixed"]')).toBeNull()
  })

  it('renders dialog title and message in body', async () => {
    const store = useUIStore()
    const promise = store.confirm({
      title: 'Are you sure?',
      message: 'This will delete everything.',
    })
    mount(AppDialog, { attachTo: document.body })
    await flushPromises()
    expect(document.body.textContent).toContain('Are you sure?')
    expect(document.body.textContent).toContain('This will delete everything.')
    store.dismissDialog()
    await promise
  })

  it('shows confirm and cancel button labels', async () => {
    const store = useUIStore()
    const promise = store.confirm({
      title: 'Delete?',
      message: 'Really?',
      confirmLabel: 'Yes delete',
      cancelLabel: 'No keep',
    })
    mount(AppDialog, { attachTo: document.body })
    await flushPromises()
    expect(document.body.textContent).toContain('Yes delete')
    expect(document.body.textContent).toContain('No keep')
    store.dismissDialog()
    await promise
  })

  it('resolves true when confirm button is clicked', async () => {
    const store = useUIStore()
    const promise = store.confirm({
      title: 'Test',
      message: 'Do it?',
      confirmLabel: 'OK',
      cancelLabel: 'Cancel',
    })
    mount(AppDialog, { attachTo: document.body })
    await flushPromises()
    // Click the button that is NOT Cancel
    const buttons = Array.from(document.body.querySelectorAll<HTMLButtonElement>('button'))
    const confirmBtn = buttons.find((b) => b.textContent?.includes('OK'))
    confirmBtn?.click()
    const result = await promise
    expect(result).toBe(true)
  })

  it('resolves false when cancel button is clicked', async () => {
    const store = useUIStore()
    const promise = store.confirm({
      title: 'Test',
      message: '',
      confirmLabel: 'OK',
      cancelLabel: 'Cancel',
    })
    mount(AppDialog, { attachTo: document.body })
    await flushPromises()
    const buttons = Array.from(document.body.querySelectorAll<HTMLButtonElement>('button'))
    const cancelBtn = buttons.find((b) => b.textContent?.includes('Cancel'))
    cancelBtn?.click()
    const result = await promise
    expect(result).toBe(false)
  })

  it('contains red color classes for danger tone', async () => {
    const store = useUIStore()
    const promise = store.confirm({ title: 'Danger!', message: '', tone: 'danger' })
    mount(AppDialog, { attachTo: document.body })
    await flushPromises()
    expect(document.body.innerHTML).toContain('red')
    store.dismissDialog()
    await promise
  })
})
