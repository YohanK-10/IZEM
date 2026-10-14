import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useUIStore } from '@/app/stores/ui'

describe('useUIStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with no active course and no dialog', () => {
    const store = useUIStore()
    expect(store.activeCourseId).toBeNull()
    expect(store.dialog).toBeNull()
  })

  describe('setActiveCourse', () => {
    it('sets and clears the active course id', () => {
      const store = useUIStore()
      store.setActiveCourse(42)
      expect(store.activeCourseId).toBe(42)
      store.setActiveCourse(null)
      expect(store.activeCourseId).toBeNull()
    })
  })

  describe('confirm dialog', () => {
    it('opens a confirm dialog and resolves true on accept', async () => {
      const store = useUIStore()
      const promise = store.confirm({ title: 'Delete?', message: 'Are you sure?' })
      expect(store.dialog).not.toBeNull()
      expect(store.dialog?.kind).toBe('confirm')
      expect(store.dialog?.title).toBe('Delete?')
      store.acceptDialog()
      expect(await promise).toBe(true)
      expect(store.dialog).toBeNull()
    })

    it('resolves false on dismiss', async () => {
      const store = useUIStore()
      const promise = store.confirm({ title: 'Delete?', message: 'Are you sure?' })
      store.dismissDialog()
      expect(await promise).toBe(false)
    })

    it('uses custom labels and tone', async () => {
      const store = useUIStore()
      const promise = store.confirm({
        title: 'Danger',
        message: 'This is destructive',
        confirmLabel: 'Yes delete',
        cancelLabel: 'No keep',
        tone: 'danger',
      })
      expect(store.dialog?.confirmLabel).toBe('Yes delete')
      expect(store.dialog?.cancelLabel).toBe('No keep')
      expect(store.dialog?.tone).toBe('danger')
      store.dismissDialog()
      await promise
    })
  })

  describe('alert dialog', () => {
    it('resolves true regardless of action', async () => {
      const store = useUIStore()
      const promise = store.alert({ title: 'Info', message: 'Done' })
      expect(store.dialog?.kind).toBe('alert')
      expect(store.dialog?.cancelLabel).toBeNull()
      store.acceptDialog()
      await expect(promise).resolves.toBeUndefined()
    })
  })

  describe('replaces an open dialog', () => {
    it('resolves the previous dialog with false when replaced', async () => {
      const store = useUIStore()
      const first = store.confirm({ title: 'First', message: '' })
      // open a second dialog before accepting the first
      const _second = store.confirm({ title: 'Second', message: '' })
      const firstResult = await first
      expect(firstResult).toBe(false)
      store.dismissDialog()
      await _second
    })
  })
})
