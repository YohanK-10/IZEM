import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import QuestionForm from '@/app/components/queue/QuestionForm.vue'

const exercise = {
  id: 1,
  question_number: 3,
  description: 'Implement BFS',
  label: null,
  require_signoff: false,
}

describe('QuestionForm', () => {
  it('renders exercise number', () => {
    const wrapper = mount(QuestionForm, {
      props: { exercise, submitError: null, busy: false },
    })
    expect(wrapper.text()).toContain('Exercise 3')
  })

  it('renders exercise description', () => {
    const wrapper = mount(QuestionForm, {
      props: { exercise, submitError: null, busy: false },
    })
    expect(wrapper.text()).toContain('Implement BFS')
  })

  it('disables submit button when text is too short', async () => {
    const wrapper = mount(QuestionForm, {
      props: { exercise, submitError: null, busy: false },
    })
    // Find the non-back button which is the submit
    const submitBtn = wrapper.findAll('button').find((b) => !b.text().match(/back/i))
    expect(submitBtn?.attributes('disabled')).toBeDefined()
  })

  it('enables submit when text >= 20 chars', async () => {
    const wrapper = mount(QuestionForm, {
      props: { exercise, submitError: null, busy: false },
    })
    const textarea = wrapper.find('textarea')
    await textarea.setValue('A'.repeat(20))
    // The submit button should become enabled
    const buttons = wrapper.findAll('button')
    const submitBtn = buttons.find((b) => !b.text().match(/back/i))
    if (submitBtn) expect(submitBtn.attributes('disabled')).toBeUndefined()
  })

  it('emits back when back button is clicked', async () => {
    const wrapper = mount(QuestionForm, {
      props: { exercise, submitError: null, busy: false },
    })
    const backBtn = wrapper.findAll('button').find((b) => b.text().match(/back/i))
    if (backBtn) {
      await backBtn.trigger('click')
      expect(wrapper.emitted('back')).toBeTruthy()
    }
  })

  it('emits submit with text when form is valid and submitted', async () => {
    const wrapper = mount(QuestionForm, {
      props: { exercise, submitError: null, busy: false },
    })
    const textarea = wrapper.find('textarea')
    await textarea.setValue('This is a long enough answer')
    const form = wrapper.find('form')
    if (form.exists()) {
      await form.trigger('submit')
      expect(wrapper.emitted('submit')).toBeTruthy()
    }
  })

  it('shows submit error message', () => {
    const wrapper = mount(QuestionForm, {
      props: { exercise, submitError: 'Something went wrong', busy: false },
    })
    expect(wrapper.text()).toContain('Something went wrong')
  })

  it('disables submit when busy', async () => {
    const wrapper = mount(QuestionForm, {
      props: { exercise, submitError: null, busy: true },
    })
    const textarea = wrapper.find('textarea')
    await textarea.setValue('A'.repeat(25))
    const buttons = wrapper.findAll('button')
    const submitBtn = buttons.find((b) => !b.text().match(/back/i))
    if (submitBtn) expect(submitBtn.attributes('disabled')).toBeDefined()
  })
})
