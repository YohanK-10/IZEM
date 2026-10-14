import { vi } from 'vitest'

// Stub window.location for tests that redirect
Object.defineProperty(window, 'location', {
  value: {
    href: '',
    pathname: '/',
    assign: vi.fn(),
    reload: vi.fn(),
  },
  writable: true,
})
