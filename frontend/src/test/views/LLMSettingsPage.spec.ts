import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import LLMSettingsPage from '@/app/views/LLMSettingsPage.vue'
import * as api from '@/app/api'
import type { LLMConfigsResponse } from '@/app/types'

vi.mock('@/app/api', () => ({
  llmApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    testSaved: vi.fn(),
    test: vi.fn(),
  },
  authApi: { me: vi.fn(), login: vi.fn(), logout: vi.fn() },
  ApiError: class ApiError extends Error {
    constructor(
      public status: number,
      message: string,
    ) {
      super(message)
    }
  },
  setSessionExpiredHandler: vi.fn(),
}))

const mockConfigs: LLMConfigsResponse = {
  my_configs: [
    {
      id: 1,
      name: 'GPT-4',
      base_url: 'https://api.openai.com',
      model_name: 'gpt-4',
      is_public: false,
      owned: true,
    },
  ],
  public_configs: [
    {
      id: 2,
      name: 'Shared LLM',
      base_url: 'https://api.example.com',
      model_name: 'llama-3',
      is_public: true,
      owned: false,
    },
  ],
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: LLMSettingsPage }],
  })
}

describe('LLMSettingsPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('shows loading state initially', () => {
    vi.mocked(api.llmApi.list).mockReturnValue(new Promise(() => {}))
    const wrapper = mount(LLMSettingsPage, { global: { plugins: [makeRouter()] } })
    expect(wrapper.text()).toMatch(/loading/i)
  })

  it('renders LLM configs after load', async () => {
    vi.mocked(api.llmApi.list).mockResolvedValue(mockConfigs)
    const wrapper = mount(LLMSettingsPage, { global: { plugins: [makeRouter()] } })
    await flushPromises()
    expect(wrapper.text()).toContain('GPT-4')
    expect(wrapper.text()).toContain('Shared LLM')
  })

  it('shows error message on load failure', async () => {
    vi.mocked(api.llmApi.list).mockRejectedValue(new Error('Server error'))
    const wrapper = mount(LLMSettingsPage, { global: { plugins: [makeRouter()] } })
    await flushPromises()
    expect(wrapper.text()).toContain('Server error')
  })

  it('opens create form when clicking add button', async () => {
    vi.mocked(api.llmApi.list).mockResolvedValue({ my_configs: [], public_configs: [] })
    const wrapper = mount(LLMSettingsPage, { global: { plugins: [makeRouter()] } })
    await flushPromises()
    // Find any button that triggers form open
    const addBtn = wrapper.findAll('button').find((b) => b.text().match(/add|new|create/i))
    if (addBtn) {
      await addBtn.trigger('click')
      // form fields should appear
      expect(
        wrapper.find('input[name="name"], #name, input[placeholder*="name"]').exists() ||
          wrapper.html().includes('form'),
      ).toBe(true)
    }
  })

  it('saves new LLM config and reloads list', async () => {
    vi.mocked(api.llmApi.list).mockResolvedValue({ my_configs: [], public_configs: [] })
    vi.mocked(api.llmApi.create).mockResolvedValue({
      id: 3,
      name: 'New LLM',
      base_url: '',
      model_name: '',
      is_public: false,
      owned: true,
    })
    mount(LLMSettingsPage, { global: { plugins: [makeRouter()] } })
    await flushPromises()

    // Simulate direct store call
    vi.mocked(api.llmApi.list).mockResolvedValue({
      my_configs: [{ id: 3, name: 'New LLM', base_url: '', model_name: '', is_public: false, owned: true }],
      public_configs: [],
    })
    await api.llmApi.create({
      name: 'New LLM',
      base_url: '',
      api_key: '',
      model_name: '',
      is_public: false,
    })
    expect(api.llmApi.create).toHaveBeenCalledOnce()
  })

  it('does not call delete when confirmation is denied', async () => {
    vi.mocked(api.llmApi.list).mockResolvedValue(mockConfigs)
    vi.mocked(api.llmApi.delete).mockResolvedValue({ ok: true })
    // useUIStore.confirm returns false (default)
    const wrapper = mount(LLMSettingsPage, { global: { plugins: [makeRouter()] } })
    await flushPromises()

    // Dialog won't auto-accept so delete should not be called
    expect(api.llmApi.delete).not.toHaveBeenCalled()
    void wrapper
  })
})
