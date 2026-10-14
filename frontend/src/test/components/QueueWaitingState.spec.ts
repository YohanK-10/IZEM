import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import QueueWaitingState from '@/app/components/queue/QueueWaitingState.vue'

const pollFn = vi.fn()

describe('QueueWaitingState', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    pollFn.mockResolvedValue({ status: 'pending', final_feedback: null })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('shows queue position', () => {
    const wrapper = mount(QueueWaitingState, {
      props: { requestId: 1, initialPosition: 5, questionText: 'Q1', pollFn },
    })
    expect(wrapper.text()).toContain('5')
  })

  it('shows question text', () => {
    const wrapper = mount(QueueWaitingState, {
      props: { requestId: 1, initialPosition: 2, questionText: 'Exercise 3', pollFn },
    })
    expect(wrapper.text()).toContain('Exercise 3')
  })

  it('emits resolved when poll returns approved status', async () => {
    pollFn.mockResolvedValue({ status: 'approved', final_feedback: 'Great work!' })
    const wrapper = mount(QueueWaitingState, {
      props: { requestId: 1, initialPosition: 1, questionText: 'Q', pollFn },
    })
    // Trigger polling
    vi.advanceTimersByTime(30_000)
    await flushPromises()
    expect(wrapper.emitted('resolved')).toBeTruthy()
    expect(wrapper.emitted('resolved')?.[0]).toEqual(['Great work!'])
  })

  it('emits resolved for edited status', async () => {
    pollFn.mockResolvedValue({ status: 'edited', final_feedback: 'Edited feedback' })
    const wrapper = mount(QueueWaitingState, {
      props: { requestId: 42, initialPosition: 3, questionText: 'Q', pollFn },
    })
    vi.advanceTimersByTime(30_000)
    await flushPromises()
    expect(wrapper.emitted('resolved')).toBeTruthy()
  })

  it('decrements position over time via countdown', async () => {
    const wrapper = mount(QueueWaitingState, {
      props: { requestId: 1, initialPosition: 5, questionText: 'Q', pollFn },
    })
    vi.advanceTimersByTime(15_000)
    await flushPromises()
    // position should have decremented
    expect(wrapper.text()).toContain('4')
  })

  it('does not decrement position below 1', async () => {
    const wrapper = mount(QueueWaitingState, {
      props: { requestId: 1, initialPosition: 1, questionText: 'Q', pollFn },
    })
    vi.advanceTimersByTime(15_000 * 3)
    await flushPromises()
    expect(wrapper.text()).not.toContain('-')
  })
})
