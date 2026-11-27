import { describe, it, expect } from 'vitest'
import {
  DESCRIPTION_WIDTH,
  assemblyLabel,
  clampWidth,
  countsSummary,
  cutterFieldRows,
  cutterSubtitle,
  diameterParts,
  draggedWidth,
  familiesIn,
  familyChoice,
  filterTally,
  formatDate,
  formatDuration,
  formatStickout,
  formatTolerance,
  formatToolNumbers,
  isAppState,
  otherUnit,
  rowKey,
  sortTally,
  stickoutParts,
  toggleSort,
  toleranceToMm,
  typeChoice,
  typesByFamily,
  validChoice,
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

describe('diameterParts', () => {
  it('shows inches alone for an inch cutter when inches are shown', () => {
    expect(diameterParts(12.7, ['inches'], 'in')).toEqual({ shown: '0.500 in', other: '' })
  })
  it('puts millimetres apart, in brackets, for a metric cutter when inches are shown', () => {
    expect(diameterParts(5, ['millimeters'], 'in')).toEqual({ shown: '0.197 in', other: '(5.00 mm)' })
  })
  it('shows millimetres alone for a metric cutter when millimetres are shown', () => {
    expect(diameterParts(6, ['millimeters'], 'mm')).toEqual({ shown: '6.00 mm', other: '' })
  })
  it('puts inches apart, in brackets, for an inch cutter when millimetres are shown', () => {
    expect(diameterParts(12.7, ['inches'], 'mm')).toEqual({ shown: '12.70 mm', other: '(0.500 in)' })
  })
  it('has both for a cutter entered both ways, whichever unit is shown', () => {
    expect(diameterParts(6.35, ['inches', 'millimeters'], 'in')).toEqual({ shown: '0.250 in', other: '(6.35 mm)' })
    expect(diameterParts(6.35, ['inches', 'millimeters'], 'mm')).toEqual({ shown: '6.35 mm', other: '(0.250 in)' })
  })
  it('shows inches to three places and millimetres to two', () => {
    expect(diameterParts(4.7625, ['inches', 'millimeters'], 'in')).toEqual({ shown: '0.188 in', other: '(4.76 mm)' })
    expect(diameterParts(10, ['inches', 'millimeters'], 'mm')).toEqual({ shown: '10.00 mm', other: '(0.394 in)' })
  })
  it('shows a dash and nothing beside it when there is no diameter', () => {
    expect(diameterParts(null, ['inches', 'millimeters'], 'in')).toEqual({ shown: '—', other: '' })
  })
})

describe('otherUnit', () => {
  it('is the unit that is not being shown', () => {
    expect([otherUnit('in'), otherUnit('mm')]).toEqual(['mm', 'in'])
  })
})

describe('stickoutParts', () => {
  it('keeps a range together in each unit', () => {
    expect(stickoutParts(40, 40.4, ['millimeters'], 'in')).toEqual({
      shown: '1.575–1.591 in',
      other: '(40.00–40.40 mm)',
    })
  })
  it('has nothing beside the shown value for a tool entered in that unit', () => {
    expect(stickoutParts(38.1, 38.1, ['inches'], 'in')).toEqual({ shown: '1.500 in', other: '' })
  })
  it('shows a dash when the stickout was not recorded', () => {
    expect(stickoutParts(null, null, ['millimeters'], 'in')).toEqual({ shown: '—', other: '' })
    expect(stickoutParts(undefined, undefined, ['millimeters'], 'in')).toEqual({ shown: '—', other: '' })
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
  it('handles no data at all', () => {
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
  it('sorts by flute count, a tool without one last when most first', () => {
    const fluted = [
      makeRow({ cutter_key: 'two', flutes: 2 }),
      makeRow({ cutter_key: 'probe', flutes: null }),
      makeRow({ cutter_key: 'four', flutes: 4 }),
    ]
    const sorted = sortTally(fluted, { key: 'flutes', direction: 'desc' })
    expect(sorted.map((r) => r.cutter_key)).toEqual(['four', 'two', 'probe'])
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
    makeRow({ cutter_key: 'c', tool_type: 'ball end mill', description: '1/4 ball' }),
  ]
  const keys = (text: string, choice: string) => filterTally(rows, text, choice).map((r) => r.cutter_key)

  it('returns everything with no text and all families', () => {
    expect(keys('', 'all')).toEqual(['a', 'b', 'c'])
  })
  it('filters by family', () => {
    expect(keys('', familyChoice('hole making'))).toEqual(['b'])
    expect(keys('', familyChoice('milling'))).toEqual(['a', 'c'])
  })
  it('filters by one tool type within a family', () => {
    expect(keys('', typeChoice('ball end mill'))).toEqual(['c'])
    expect(keys('', typeChoice('flat end mill'))).toEqual(['a'])
  })
  it('does not take a tool type for a family of the same name, or the other way round', () => {
    const named = [makeRow({ cutter_key: 'x', family: 'drill', tool_type: 'milling' })]
    expect(filterTally(named, '', typeChoice('drill'))).toEqual([])
    expect(filterTally(named, '', familyChoice('milling'))).toEqual([])
  })
  it('matches description text without regard to case or padding', () => {
    expect(keys('  FLAT ', 'all')).toEqual(['a'])
  })
  it('matches a tool number with or without the T', () => {
    expect(keys('t1202', 'all')).toEqual(['b'])
    expect(keys('1202', 'all')).toEqual(['b'])
  })
  it('combines text with a family or a tool type', () => {
    expect(keys('drill', familyChoice('milling'))).toEqual([])
    expect(keys('ball', typeChoice('flat end mill'))).toEqual([])
    expect(keys('ball', typeChoice('ball end mill'))).toEqual(['c'])
  })
})

describe('typesByFamily', () => {
  it('lists the milling and hole making types that were found, A to Z, milling first', () => {
    const rows = [
      makeRow({ tool_type: 'flat end mill' }),
      makeRow({ tool_type: 'reamer', family: 'hole making' }),
      makeRow({ tool_type: 'ball end mill' }),
      makeRow({ tool_type: 'drill', family: 'hole making' }),
      makeRow({ tool_type: 'flat end mill' }),
    ]
    expect(typesByFamily(rows)).toEqual([
      { family: 'milling', types: ['ball end mill', 'flat end mill'] },
      { family: 'hole making', types: ['drill', 'reamer'] },
    ])
  })
  it('leaves out probes, holders and other tools', () => {
    const rows = [
      makeRow({ tool_type: 'probe', family: 'probe' }),
      makeRow({ tool_type: 'holder', family: 'holder' }),
      makeRow({ tool_type: 'engraver', family: 'other' }),
      makeRow({ tool_type: 'drill', family: 'hole making' }),
    ]
    expect(typesByFamily(rows)).toEqual([{ family: 'hole making', types: ['drill'] }])
  })
  it('lists nothing when nothing was found', () => {
    expect(typesByFamily([])).toEqual([])
  })
})

describe('validChoice', () => {
  const rows = [makeRow({ tool_type: 'drill', family: 'hole making' })]

  it('keeps a choice the data still has', () => {
    expect(validChoice(rows, typeChoice('drill'))).toBe('type:drill')
    expect(validChoice(rows, familyChoice('hole making'))).toBe('family:hole making')
    expect(validChoice(rows, 'all')).toBe('all')
  })
  it('falls back to everything when the data no longer has the choice', () => {
    expect(validChoice(rows, typeChoice('reamer'))).toBe('all')
    expect(validChoice(rows, familyChoice('milling'))).toBe('all')
    expect(validChoice([], typeChoice('drill'))).toBe('all')
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
    expect(isAppState({ counts: { documents: 0, observations: 0, cutters: 0 }, tally: [] })).toBe(true)
  })
  it('rejects an error reply and a missing reply', () => {
    expect(isAppState({ error: 'Internal error' })).toBe(false)
    expect(isAppState({ tally: [] })).toBe(false)
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
    expect(formatStickout(38.1, 38.1, ['inches'], 'in')).toBe('1.500 in')
  })

  it('shows the range an assembly covers', () => {
    expect(formatStickout(38.1, 38.354, ['inches'], 'in')).toBe('1.500–1.510 in')
  })

  it('puts the range in both units for a metric tool when inches are shown', () => {
    expect(formatStickout(40, 40.4, ['millimeters'], 'in')).toBe('1.575–1.591 in (40.00–40.40 mm)')
    expect(formatStickout(40, 40, ['millimeters'], 'in')).toBe('1.575 in (40.00 mm)')
  })

  it('follows the unit that is shown', () => {
    expect(formatStickout(40, 40.4, ['millimeters'], 'mm')).toBe('40.00–40.40 mm')
    expect(formatStickout(38.1, 38.354, ['inches'], 'mm')).toBe('38.10–38.35 mm (1.500–1.510 in)')
  })

  it('shows a dash when the stickout was not recorded', () => {
    expect(formatStickout(null, null, ['inches'], 'in')).toBe('—')
    expect(formatStickout(undefined, undefined, ['inches'], 'in')).toBe('—')
  })

  it('shows zero stickout as a value, not as missing', () => {
    expect(formatStickout(0, 0, ['inches'], 'in')).toBe('0.000 in')
  })
})

describe('formatTolerance', () => {
  it('always shows both units, the shown one first', () => {
    expect(formatTolerance(0.5, 'in')).toBe('0.020 in (0.50 mm)')
    expect(formatTolerance(0.5, 'mm')).toBe('0.50 mm (0.020 in)')
    expect(formatTolerance(0, 'in')).toBe('0.000 in (0.00 mm)')
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

describe('cutterFieldRows', () => {
  it('labels the geometry in a fixed order, whatever order it arrives in', () => {
    const fields = { material: 'carbide', OAL: 76.2, NOF: 3, DC: 12.7, LCF: 31.75 }
    expect(cutterFieldRows(fields, ['inches'], 'in')).toEqual([
      { label: 'Diameter', value: '0.500 in', other: '' },
      { label: 'Flutes', value: '3', other: '' },
      { label: 'Flute length', value: '1.250 in', other: '' },
      { label: 'Overall length', value: '3.000 in', other: '' },
      { label: 'Material', value: 'carbide', other: '' },
    ])
  })
  it('gives the lengths of a metric cutter both units, but never angles or counts', () => {
    const fields = { DC: 5, NOF: 2, SIG: 118, TA: 0.5 }
    expect(cutterFieldRows(fields, ['millimeters'], 'in')).toEqual([
      { label: 'Diameter', value: '0.197 in', other: '(5.00 mm)' },
      { label: 'Flutes', value: '2', other: '' },
      { label: 'Taper angle', value: '0.5°', other: '' },
      { label: 'Tip angle', value: '118°', other: '' },
    ])
  })
  it('follows the unit that is shown', () => {
    expect(cutterFieldRows({ DC: 5 }, ['millimeters'], 'mm')).toEqual([
      { label: 'Diameter', value: '5.00 mm', other: '' },
    ])
    expect(cutterFieldRows({ DC: 12.7 }, ['inches'], 'mm')).toEqual([
      { label: 'Diameter', value: '12.70 mm', other: '(0.500 in)' },
    ])
  })
  it('names every length the fingerprint uses', () => {
    const fields = { 'shoulder-length': 20, SFDM: 10, RE: 0.5, 'tip-diameter': 1, TP: 1.25 }
    expect(cutterFieldRows(fields, ['millimeters'], 'mm').map((row) => row.label)).toEqual([
      'Shoulder length',
      'Shaft diameter',
      'Corner radius',
      'Tip diameter',
      'Thread pitch',
    ])
  })
  it('leaves out a blank material and fields it does not know', () => {
    expect(cutterFieldRows({ DC: 3, material: '', mystery: 9 }, ['millimeters'], 'mm')).toEqual([
      { label: 'Diameter', value: '3.00 mm', other: '' },
    ])
  })
})

describe('cutterSubtitle', () => {
  it('names the type and the material', () => {
    expect(cutterSubtitle({ tool_type: 'flat end mill', fields: { material: 'carbide' } })).toBe(
      'flat end mill · carbide',
    )
  })
  it('leaves out a material that is blank, missing or unspecified', () => {
    expect(cutterSubtitle({ tool_type: 'drill', fields: { material: 'unspecified' } })).toBe('drill')
    expect(cutterSubtitle({ tool_type: 'drill', fields: { material: '' } })).toBe('drill')
    expect(cutterSubtitle({ tool_type: 'drill', fields: { DC: 5 } })).toBe('drill')
  })
})

describe('assemblyLabel', () => {
  const assembly = (overrides: object) => ({
    assembly_key: 'k',
    holder: 'Test Holder',
    stickout_min_mm: 38.1,
    stickout_max_mm: 38.1,
    programs: 3,
    operations: 4,
    time_s: 60,
    ...overrides,
  })

  it('names the holder and the stickout in the shown unit', () => {
    expect(assemblyLabel(assembly({}), ['inches'], 'in')).toBe('Test Holder, 1.500 in')
    expect(assemblyLabel(assembly({}), ['inches'], 'mm')).toBe('Test Holder, 38.10 mm (1.500 in)')
  })
  it('shows the range an assembly covers', () => {
    expect(assemblyLabel(assembly({ stickout_max_mm: 38.354 }), ['inches'], 'in')).toBe(
      'Test Holder, 1.500–1.510 in',
    )
  })
  it('says so when there is no holder', () => {
    expect(assemblyLabel(assembly({ holder: '' }), ['inches'], 'in')).toBe('no holder, 1.500 in')
  })
  it('leaves the stickout out when it was not recorded', () => {
    expect(assemblyLabel(assembly({ stickout_min_mm: null, stickout_max_mm: null }), ['inches'], 'in')).toBe(
      'Test Holder',
    )
  })
})

describe('clampWidth', () => {
  it('keeps a width inside the limits as it is', () => {
    expect(clampWidth(240)).toBe(240)
    expect(clampWidth(DESCRIPTION_WIDTH.min)).toBe(80)
    expect(clampWidth(DESCRIPTION_WIDTH.max)).toBe(1000)
  })
  it('brings a remembered width back inside the limits', () => {
    expect(clampWidth(5)).toBe(80)
    expect(clampWidth(4000)).toBe(1000)
  })
  it('lands on a whole pixel', () => {
    expect(clampWidth(240.6)).toBe(241)
  })
})

describe('draggedWidth', () => {
  it('follows the drag, wider to the right and narrower to the left', () => {
    expect(draggedWidth(240, 60)).toBe(300)
    expect(draggedWidth(240, -40)).toBe(200)
    expect(draggedWidth(240, 0)).toBe(240)
  })
  it('measures from where the drag began', () => {
    expect(draggedWidth(500, 25)).toBe(525)
  })
  it('never goes narrower than the least width, however far left', () => {
    expect(draggedWidth(240, -200)).toBe(80)
    expect(draggedWidth(240, -5000)).toBe(80)
  })
  it('never goes wider than the most width', () => {
    expect(draggedWidth(240, 5000)).toBe(1000)
  })
})
