import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { api, ApiError, setSessionExpiredHandler } from '@/app/api/client'

function mockFetch(status: number, body: unknown, headers: Record<string, string> = {}) {
  const response = new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))
}

describe('api client', () => {
  beforeEach(() => {
    window.location.pathname = '/'
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  describe('successful requests', () => {
    it('GET returns parsed JSON', async () => {
      mockFetch(200, { id: 1, name: 'Test' })
      const result = await api.get('/test')
      expect(result).toEqual({ id: 1, name: 'Test' })
    })

    it('POST sends JSON body with correct Content-Type', async () => {
      mockFetch(200, { ok: true })
      await api.post('/test', { foo: 'bar' })
      const fetchCall = vi.mocked(fetch).mock.calls[0]
      const init = fetchCall[1] as RequestInit
      expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json')
      expect(init.body).toBe(JSON.stringify({ foo: 'bar' }))
    })

    it('PUT sends JSON body', async () => {
      mockFetch(200, { ok: true })
      await api.put('/test', { updated: true })
      const fetchCall = vi.mocked(fetch).mock.calls[0]
      expect((fetchCall[1] as RequestInit).method).toBe('PUT')
    })

    it('DELETE sends DELETE method', async () => {
      mockFetch(200, { ok: true })
      await api.delete('/test')
      const fetchCall = vi.mocked(fetch).mock.calls[0]
      expect((fetchCall[1] as RequestInit).method).toBe('DELETE')
    })

    it('204 No Content returns undefined', async () => {
      mockFetch(204, null)
      const result = await api.get('/test')
      expect(result).toBeUndefined()
    })

    it('includes credentials: include', async () => {
      mockFetch(200, {})
      await api.get('/test')
      const fetchCall = vi.mocked(fetch).mock.calls[0]
      expect((fetchCall[1] as RequestInit).credentials).toBe('include')
    })
  })

  describe('error handling', () => {
    it('throws ApiError with status and message for non-2xx', async () => {
      mockFetch(404, { detail: 'Not found' })
      await expect(api.get('/missing')).rejects.toMatchObject({
        status: 404,
        message: 'Not found',
      })
    })

    it('throws ApiError with fallback message when body has no detail', async () => {
      mockFetch(500, { error: 'something broke' })
      await expect(api.get('/error')).rejects.toMatchObject({
        status: 500,
        message: 'HTTP 500',
      })
    })

    it('ApiError is instanceof Error', async () => {
      mockFetch(400, { detail: 'Bad' })
      try {
        await api.get('/bad')
      } catch (e) {
        expect(e).toBeInstanceOf(Error)
        expect(e).toBeInstanceOf(ApiError)
      }
    })
  })

  describe('401 handling', () => {
    it('calls sessionExpiredHandler and throws for non-silent 401 paths', async () => {
      mockFetch(401, { detail: 'Session expired' })
      const handler = vi.fn()
      setSessionExpiredHandler(handler)
      window.location.pathname = '/courses'
      await expect(api.get('/courses')).rejects.toThrow()
      expect(handler).toHaveBeenCalled()
    })

    it('does NOT call handler for /api/me (silent path)', async () => {
      mockFetch(401, { detail: 'Unauthorized' })
      const handler = vi.fn()
      setSessionExpiredHandler(handler)
      await expect(api.get('/me')).rejects.toMatchObject({ status: 401 })
      expect(handler).not.toHaveBeenCalled()
    })

    it('does NOT call handler for /api/auth/login (silent path)', async () => {
      mockFetch(401, { detail: 'Unauthorized' })
      const handler = vi.fn()
      setSessionExpiredHandler(handler)
      await expect(api.post('/auth/login', {})).rejects.toMatchObject({ status: 401 })
      expect(handler).not.toHaveBeenCalled()
    })

    it('does NOT call handler when already on /login page', async () => {
      mockFetch(401, { detail: 'Unauthorized' })
      const handler = vi.fn()
      setSessionExpiredHandler(handler)
      window.location.pathname = '/login'
      await expect(api.get('/some-protected-route')).rejects.toThrow()
      expect(handler).not.toHaveBeenCalled()
    })
  })

  describe('postForm', () => {
    it('sends FormData without Content-Type header', async () => {
      mockFetch(200, { ok: true })
      const form = new FormData()
      form.append('file', 'data')
      await api.postForm('/upload', form)
      const fetchCall = vi.mocked(fetch).mock.calls[0]
      const init = fetchCall[1] as RequestInit
      expect((init.headers as Record<string, string>)['Content-Type']).toBeUndefined()
      expect(init.body).toBe(form)
    })
  })
})
