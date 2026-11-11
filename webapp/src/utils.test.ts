import { describe, it, expect } from 'vitest'
import {
  countsSummary,
  datasetBadge,
  familiesIn,
  filterTally,
  formatDate,
  formatDiameter,
  formatDuration,
  formatToolNumbers,
  isAppState,
  sortTally,
  toggleSort,
} from './utils'
import type { TallyRow } from './types'

function makeRow(overrides?: Partial<TallyRow>): TallyRow {
  return {
    cutter_key: 'aaaa',
    tool_type: 'flat end mill',
    family: 'milling',
    description: '1/2 flat end mill',
    diameter_mm: 12.7,
    flutes: 3,
    programs: 2,
    operations: 5,
    time_s: 600,
    operations_without_time: 0,
    first_used: 1_700_000_000,
    last_used: 1_700_086_400,
    tool_numbers: [7],
    machines: ['Example Mill'],
    units: ['inches'],
    ...overrides,
  }
}

describe('formatDuration', () => {
  it('shows seconds under a minute', () => {
    expect(formatDuration(0)).toBe('0s')
    expect(formatDuration(45.4)).toBe('45s')
  })
  it('shows minutes and padded seconds', () => {
    expect(formatDuration(125)).toBe('2m 05s')
  })
  it('shows hours and padded minutes', () => {
    expect(formatDuration(3725)).toBe('1h 02m')
  })
  it('rolls 59.6 seconds over to a minute', () => {
    expect(formatDuration(59.6)).toBe('1m 00s')
  })
})

describe('formatDiameter', () => {
  it('shows millimetres only for a metric cutter', () => {
    expect(formatDiameter(6, ['millimeters'])).toBe('6.000 mm')
  })
  it('adds inches when the cutter was entered in inches', () => {
    expect(formatDiameter(12.7, ['inches'])).toBe('12.700 mm / 0.5000 in')
    expect(formatDiameter(6.35, ['inches', 'millimeters'])).toBe('6.350 mm / 0.2500 in')
  })
  it('shows a dash when there is no diameter', () => {
    expect(formatDiameter(null, ['inches'])).toBe('—')
  })
})

describe('formatDate', () => {
  it('formats epoch seconds as a local calendar date', () => {
    // Noon UTC is the same calendar day in every time zone from UTC-12 to UTC+11.
    expect(formatDate(Date.UTC(2026, 2, 5, 12) / 1000)).toBe('2026-03-05')
  })
})

describe('formatToolNumbers', () => {
  it('prefixes each number with T', () => {
    expect(formatToolNumbers([7, 344])).toBe('T7, T344')
  })
  it('is empty when there are none', () => {
    expect(formatToolNumbers([])).toBe('')
  })
})

describe('datasetBadge', () => {
  it('labels the two datasets differently', () => {
    expect(datasetBadge('trial')).toEqual({ label: 'TRIAL DATA', tone: 'trial' })
    expect(datasetBadge('main')).toEqual({ label: 'MAIN DATA', tone: 'main' })
  })
})

describe('countsSummary', () => {
  it('pluralizes each count', () => {
    expect(countsSummary({ documents: 3, observations: 118, cutters: 22 })).toBe(
      '3 programs, 118 operations, 22 cutters',
    )
  })
  it('uses the singular for one', () => {
    expect(countsSummary({ documents: 1, observations: 1, cutters: 1 })).toBe(
      '1 program, 1 operation, 1 cutter',
    )
  })
  it('handles an empty dataset', () => {
    expect(countsSummary({ documents: 0, observations: 0, cutters: 0 })).toBe(
      '0 programs, 0 operations, 0 cutters',
    )
  })
})

describe('toggleSort', () => {
  it('flips direction on the same column', () => {
    expect(toggleSort({ key: 'operations', direction: 'desc' }, 'operations')).toEqual({
      key: 'operations',
      direction: 'asc',
    })
  })
  it('starts a number column largest first', () => {
    expect(toggleSort({ key: 'operations', direction: 'asc' }, 'programs')).toEqual({
      key: 'programs',
      direction: 'desc',
    })
  })
  it('starts a text column A to Z', () => {
    expect(toggleSort({ key: 'operations', direction: 'desc' }, 'tool_type')).toEqual({
      key: 'tool_type',
      direction: 'asc',
    })
  })
})

describe('sortTally', () => {
  const rows = [
    makeRow({ cutter_key: 'b', operations: 2, tool_type: 'drill', diameter_mm: 5 }),
    makeRow({ cutter_key: 'a', operations: 9, tool_type: 'flat end mill', diameter_mm: 12.7 }),
    makeRow({ cutter_key: 'c', operations: 2, tool_type: 'chamfer mill', diameter_mm: null }),
  ]

  it('sorts numbers descending and breaks ties by cutter key', () => {
    const sorted = sortTally(rows, { key: 'operations', direction: 'desc' })
    expect(sorted.map((r) => r.cutter_key)).toEqual(['a', 'b', 'c'])
  })
  it('sorts numbers ascending', () => {
    const sorted = sortTally(rows, { key: 'operations', direction: 'asc' })
    expect(sorted.map((r) => r.cutter_key)).toEqual(['b', 'c', 'a'])
  })
  it('sorts text alphabetically', () => {
    const sorted = sortTally(rows, { key: 'tool_type', direction: 'asc' })
    expect(sorted.map((r) => r.tool_type)).toEqual(['chamfer mill', 'drill', 'flat end mill'])
  })
  it('puts a missing diameter last when largest first', () => {
    const sorted = sortTally(rows, { key: 'diameter_mm', direction: 'desc' })
    expect(sorted.map((r) => r.diameter_mm)).toEqual([12.7, 5, null])
  })
  it('does not change the input array', () => {
    sortTally(rows, { key: 'operations', direction: 'desc' })
    expect(rows.map((r) => r.cutter_key)).toEqual(['b', 'a', 'c'])
  })
  it('handles empty and single-row lists', () => {
    expect(sortTally([], { key: 'operations', direction: 'desc' })).toEqual([])
    expect(sortTally([rows[0]], { key: 'operations', direction: 'desc' })).toEqual([rows[0]])
  })
})

describe('filterTally', () => {
  const rows = [
    makeRow({ cutter_key: 'a' }),
    makeRow({
      cutter_key: 'b',
      tool_type: 'drill',
      family: 'hole making',
      description: '5 mm drill',
      tool_numbers: [12, 1202],
    }),
  ]

  it('returns everything with no text and all families', () => {
    expect(filterTally(rows, '', 'all').map((r) => r.cutter_key)).toEqual(['a', 'b'])
  })
  it('filters by family', () => {
    expect(filterTally(rows, '', 'hole making').map((r) => r.cutter_key)).toEqual(['b'])
  })
  it('matches description text without regard to case or padding', () => {
    expect(filterTally(rows, '  FLAT ', 'all').map((r) => r.cutter_key)).toEqual(['a'])
  })
  it('matches a tool number with or without the T', () => {
    expect(filterTally(rows, 't1202', 'all').map((r) => r.cutter_key)).toEqual(['b'])
    expect(filterTally(rows, '1202', 'all').map((r) => r.cutter_key)).toEqual(['b'])
  })
  it('combines text and family', () => {
    expect(filterTally(rows, 'drill', 'milling')).toEqual([])
  })
})

describe('familiesIn', () => {
  it('lists each family once, sorted', () => {
    const rows = [
      makeRow({ family: 'milling' }),
      makeRow({ family: 'hole making' }),
      makeRow({ family: 'milling' }),
    ]
    expect(familiesIn(rows)).toEqual(['hole making', 'milling'])
  })
  it('is empty for no rows', () => {
    expect(familiesIn([])).toEqual([])
  })
})

describe('isAppState', () => {
  it('accepts a state from Python', () => {
    expect(isAppState({ dataset: 'trial', tally: [] })).toBe(true)
  })
  it('rejects an error reply and a missing reply', () => {
    expect(isAppState({ error: 'Internal error' })).toBe(false)
    expect(isAppState(null)).toBe(false)
  })
})
