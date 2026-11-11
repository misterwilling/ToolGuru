import { describe, it, expect } from 'vitest'
import { formatSlot } from './utils'

describe('formatSlot', () => {
  it('capitalizes the first letter', () => {
    expect(formatSlot('primary')).toBe('Primary')
  })

  it('replaces underscores with spaces', () => {
    expect(formatSlot('secondary_target')).toBe('Secondary target')
  })

  it('handles empty input', () => {
    expect(formatSlot('')).toBe('')
  })
})
