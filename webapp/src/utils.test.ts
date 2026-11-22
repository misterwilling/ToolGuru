import { describe, it, expect } from 'vitest'
import {
  countsSummary,
  datasetBadge,
  familiesIn,
  filterTally,
  formatDate,
  formatDiameter,
  formatDuration,
  formatStickout,
  formatTolerance,
  formatToolNumbers,
  isAppState,
  rowKey,
  sortTally,
  toggleSort,
  toleranceToMm,
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
  it('counts assemblies instead of cutters when counting by assembly', () => {
    expect(countsSummary({ documents: 3, observations: 117, cutters: 24 }, 26)).toBe(
      '3 programs, 117 operations, 26 assemblies',
    )
  })
  it('uses the singular for one assembly and handles none', () => {
    expect(countsSummary({ documents: 1, observations: 1, cutters: 1 }, 1)).toBe(
      '1 program, 1 operation, 1 assembly',
    )
    expect(countsSummary({ documents: 0, observations: 0, cutters: 0 }, 0)).toBe(
      '0 programs, 0 operations, 0 assemblies',
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

describe('rowKey', () => {
  it('is the cutter key when counting by cutter', () => {
    expect(rowKey(makeRow({ cutter_key: 'c1' }))).toBe('c1')
  })

  it('is the assembly key when counting by assembly', () => {
    expect(rowKey(makeRow({ cutter_key: 'c1', assembly_key: 'c1|id:th-100|38.100' }))).toBe(
      'c1|id:th-100|38.100',
    )
  })
})

describe('formatStickout', () => {
  it('shows one value when every use had the same stickout', () => {
    expect(formatStickout(38.1, 38.1, ['inches'])).toBe('38.100 mm / 1.5000 in')
  })

  it('shows the range an assembly covers', () => {
    expect(formatStickout(38.1, 38.354, ['inches'])).toBe('38.100–38.354 mm / 1.5000–1.5100 in')
  })

  it('leaves inches out for a tool only ever entered in millimetres', () => {
    expect(formatStickout(40, 40.4, ['millimeters'])).toBe('40.000–40.400 mm')
    expect(formatStickout(40, 40, ['millimeters'])).toBe('40.000 mm')
  })

  it('shows a dash when the stickout was not recorded', () => {
    expect(formatStickout(null, null, ['inches'])).toBe('—')
    expect(formatStickout(undefined, undefined, ['inches'])).toBe('—')
  })

  it('shows zero stickout as a value, not as missing', () => {
    expect(formatStickout(0, 0, ['millimeters'])).toBe('0.000 mm')
  })
})

describe('formatTolerance', () => {
  it('shows millimetres and inches', () => {
    expect(formatTolerance(0.5)).toBe('0.500 mm / 0.0197 in')
    expect(formatTolerance(0)).toBe('0.000 mm / 0.0000 in')
  })
})

describe('toleranceToMm', () => {
  it('converts inches to millimetres', () => {
    expect(toleranceToMm('0.020', 'in')).toBe(0.508)
    expect(toleranceToMm('.01', 'in')).toBe(0.254)
  })

  it('keeps millimetres as typed', () => {
    expect(toleranceToMm('0.5', 'mm')).toBe(0.5)
  })

  it('accepts zero, meaning an exact match', () => {
    expect(toleranceToMm('0', 'in')).toBe(0)
  })

  it('refuses blank, negative and non-numeric entries', () => {
    expect(toleranceToMm('', 'mm')).toBeNull()
    expect(toleranceToMm('   ', 'mm')).toBeNull()
    expect(toleranceToMm('-0.1', 'mm')).toBeNull()
    expect(toleranceToMm('wide', 'in')).toBeNull()
    expect(toleranceToMm('Infinity', 'mm')).toBeNull()
  })
})

describe('assembly rows in the table', () => {
  const short = makeRow({ assembly_key: 'c1|id:a|38.100', holder: 'ER32 short', operations: 4 })
  const long = makeRow({ assembly_key: 'c1|id:b|38.100', holder: 'Shrink fit long', operations: 4 })

  it('filters by holder name', () => {
    expect(filterTally([short, long], 'shrink', 'all')).toEqual([long])
  })

  it('keeps two assemblies of one cutter in a stable order when the sort column ties', () => {
    const sort = { key: 'operations', direction: 'desc' } as const
    expect(sortTally([long, short], sort)).toEqual([short, long])
    expect(sortTally([short, long], sort)).toEqual([short, long])
  })
})
