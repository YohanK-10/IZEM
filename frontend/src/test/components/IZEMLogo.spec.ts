import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import IZEMLogo from '@/app/components/IZEMLogo.vue'

describe('IZEMLogo', () => {
  it('renders an SVG element', () => {
    const wrapper = mount(IZEMLogo)
    expect(wrapper.find('svg').exists()).toBe(true)
  })

  it('uses the default size of 40', () => {
    const wrapper = mount(IZEMLogo)
    const svg = wrapper.find('svg')
    expect(svg.attributes('width')).toBe('40')
    expect(svg.attributes('height')).toBe('40')
  })

  it('accepts a custom size prop', () => {
    const wrapper = mount(IZEMLogo, { props: { size: 64 } })
    const svg = wrapper.find('svg')
    expect(svg.attributes('width')).toBe('64')
    expect(svg.attributes('height')).toBe('64')
  })

  it('renders logo shape paths', () => {
    const wrapper = mount(IZEMLogo)
    expect(wrapper.find('path').exists()).toBe(true)
  })
})
