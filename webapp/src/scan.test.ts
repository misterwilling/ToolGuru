import { describe, it, expect } from 'vitest'
import { browserHere, isAppState, scanHeadline, scanOutcome, scanPercent } from './utils'
import type { ScanJob } from './types'

function makeScan(overrides?: Partial<ScanJob>): ScanJob {
  return {
    folder: 'Project / Folder',
    total: 40,
    pending: 28,
    scanned: 10,
    skipped: 1,
    failed: 1,
    problems: [],
    running: true,
    ...overrides,
  }
}

describe('scanPercent', () => {
  it('counts skipped and failed programs as done, not only scanned ones', () => {
    expect(scanPercent(makeScan())).toBe(30)
  })
  it('is 0 before the first program and 100 after the last', () => {
    expect(scanPercent(makeScan({ pending: 40, scanned: 0, skipped: 0, failed: 0 }))).toBe(0)
    expect(scanPercent(makeScan({ pending: 0, scanned: 38 }))).toBe(100)
  })
  it('rounds to a whole percent', () => {
    expect(scanPercent(makeScan({ total: 3, pending: 2 }))).toBe(33)
  })
  it('does not divide by zero for an empty scan', () => {
    expect(scanPercent(makeScan({ total: 0, pending: 0 }))).toBe(100)
  })
})

describe('scanHeadline', () => {
  it('shows progress while running', () => {
    expect(scanHeadline(makeScan())).toBe('Scanning “Project / Folder”: 12 of 40')
  })
  it('says paused when programs are left and the scan is not running', () => {
    expect(scanHeadline(makeScan({ running: false }))).toBe(
      'Scan of “Project / Folder” paused at 12 of 40',
    )
  })
  it('says finished when nothing is left', () => {
    expect(scanHeadline(makeScan({ running: false, pending: 0, scanned: 38 }))).toBe(
      'Scan of “Project / Folder” finished: 40 of 40',
    )
  })
})

describe('scanOutcome', () => {
  it('lists the three outcomes', () => {
    expect(scanOutcome(makeScan())).toBe('10 scanned, 1 skipped, 1 failed')
  })
})

describe('browserHere', () => {
  const folder = { folderId: 'f', path: [], folders: [] }
  it('asks for a project at the top level', () => {
    expect(browserHere({ ...folder, folderId: '', programs: 0 })).toBe('Choose a project.')
  })
  it('counts the designs directly in a folder', () => {
    expect(browserHere({ ...folder, programs: 3 })).toBe('3 Fusion designs directly in this folder.')
    expect(browserHere({ ...folder, programs: 1 })).toBe('1 Fusion design directly in this folder.')
    expect(browserHere({ ...folder, programs: 0 })).toBe('0 Fusion designs directly in this folder.')
  })
})

describe('a state pushed during a scan', () => {
  it('is accepted like a reply, and anything else is not', () => {
    expect(isAppState({ counts: {}, tally: [], scan: makeScan() })).toBe(true)
    expect(isAppState('{}')).toBe(false)
  })
})
