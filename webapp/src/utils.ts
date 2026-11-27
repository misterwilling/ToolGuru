// Pure utility functions — no React, no DOM, no bridge. Everything that
// doesn't need a browser goes here so it's directly testable with Vitest.

import type {
  AppState,
  Browser,
  ConfirmScan,
  Counts,
  CutterDetail,
  CutterFields,
  DetailAssembly,
  DetailPreset,
  LengthUnit,
  SavedDatabase,
  SimilarGroup,
  SimilarMember,
  ScanJob,
  SortKey,
  Speeds,
  SortState,
  TallyRow,
} from './types'

const MM_PER_INCH = 25.4
const TEXT_KEYS: SortKey[] = ['tool_type', 'description']

export function isAppState(value: unknown): value is AppState {
  return typeof value === 'object' && value !== null && 'counts' in value && 'tally' in value
}

export function formatDuration(seconds: number): string {
  const total = Math.round(seconds)
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const secs = total % 60
  const two = (n: number): string => String(n).padStart(2, '0')
  if (hours > 0) return `${hours}h ${two(minutes)}m`
  if (minutes > 0) return `${minutes}m ${two(secs)}s`
  return `${secs}s`
}

// Lengths are stored in millimetres and shown in the unit the user chose. A
// tool that was entered in the other unit shows that one too, after it:
// "0.197 in" then "5.00 mm" for a metric drill when inches are shown. Inches
// are shown to three decimal places and millimetres to two.

/**
 * A length ready for a table. `shown` is in the unit the user chose; `other`
 * is the same length in the other unit, or '' when the tool was not entered in it.
 * Kept apart so each can sit in its own column: every `shown` value then
 * lines up, whether or not the row has an `other`.
 */
export interface LengthParts {
  shown: string
  other: string
}

const NO_LENGTH: LengthParts = { shown: '—', other: '' }

export function otherUnit(display: LengthUnit): LengthUnit {
  return display === 'in' ? 'mm' : 'in'
}

function inUnit(mm: number, unit: LengthUnit): string {
  return unit === 'in' ? (mm / MM_PER_INCH).toFixed(3) : mm.toFixed(2)
}

/**
 * One length, or a range when `max` differs from `min`. `both` adds the other
 * unit. `named` puts the unit after each figure ("0.500 in"); a column that
 * names its unit in the heading asks for the bare figure ("0.500").
 */
function lengthParts(min: number, max: number, display: LengthUnit, both: boolean, named: boolean): LengthParts {
  const text = (unit: LengthUnit): string => {
    const figures = min === max ? inUnit(min, unit) : `${inUnit(min, unit)}–${inUnit(max, unit)}`
    return named ? `${figures} ${unit}` : figures
  }
  return { shown: text(display), other: both ? text(otherUnit(display)) : '' }
}

/** A column heading that names its unit, so the rows under it need not: "Dia(in)". */
export function unitHeading(label: string, unit: LengthUnit): string {
  return `${label}(${unit})`
}

/** What sets the two units apart in one piece of text: an em space, wider than a word space. */
export const UNIT_GAP = '\u2003'

function joined(parts: LengthParts): string {
  return parts.other === '' ? parts.shown : `${parts.shown}${UNIT_GAP}${parts.other}`
}

/** True when the tool was ever entered in the unit that is not the one shown. */
function enteredInOtherUnit(units: string[], display: LengthUnit): boolean {
  return units.includes(display === 'in' ? 'millimeters' : 'inches')
}

/** A diameter for the list, as bare figures: the column headings name the units. */
export function diameterParts(mm: number | null, units: string[], display: LengthUnit): LengthParts {
  return mm === null ? NO_LENGTH : lengthParts(mm, mm, display, enteredInOtherUnit(units, display), false)
}

/** One row per cutter, or per assembly when counting by assembly. */
export function rowKey(row: TallyRow): string {
  return row.assembly_key ?? row.cutter_key
}

function stickoutLength(
  min: number | null | undefined,
  max: number | null | undefined,
  units: string[],
  display: LengthUnit,
  named: boolean,
): LengthParts {
  if (min === null || min === undefined || max === null || max === undefined) return NO_LENGTH
  return lengthParts(min, max, display, enteredInOtherUnit(units, display), named)
}

/**
 * A single stickout, or the range an assembly row covers, for the list: bare
 * figures, because the column headings name the units.
 */
export function stickoutParts(
  min: number | null | undefined,
  max: number | null | undefined,
  units: string[],
  display: LengthUnit,
): LengthParts {
  return stickoutLength(min, max, units, display, false)
}

/** A stickout as one piece of text with its units, for a sentence or a label. */
export function formatStickout(
  min: number | null | undefined,
  max: number | null | undefined,
  units: string[],
  display: LengthUnit,
): string {
  return joined(stickoutLength(min, max, units, display, true))
}

/** A tolerance belongs to no tool, so it always shows both units. */
export function formatTolerance(mm: number, display: LengthUnit): string {
  return joined(lengthParts(mm, mm, display, true, true))
}

/** What the user typed as a tolerance, in millimetres; null when it is not zero or more. */
export function toleranceToMm(text: string, unit: LengthUnit): number | null {
  if (text.trim() === '') return null
  const value = Number(text)
  if (!Number.isFinite(value) || value < 0) return null
  const mm = unit === 'in' ? value * MM_PER_INCH : value
  return Math.round(mm * 1000) / 1000
}

export function formatDate(epochSeconds: number): string {
  const date = new Date(epochSeconds * 1000)
  const two = (n: number): string => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${two(date.getMonth() + 1)}-${two(date.getDate())}`
}

export function formatToolNumbers(numbers: number[]): string {
  return numbers.map((n) => `T${n}`).join(', ')
}

function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? '' : 's'}`
}

export type StatKind = 'programs' | 'operations' | 'cutters' | 'assemblies'

/** One figure of what has been scanned: "1,856" "operations". */
export interface StatItem {
  kind: StatKind
  value: string
  label: string
}

/**
 * What has been scanned, as three figures: programs, operations, and cutters.
 * Pass `assemblies` when counting by assembly, so the third figure counts
 * what the table counts.
 */
export function statItems(counts: Counts, assemblies?: number): StatItem[] {
  const item = (kind: StatKind, count: number, one: string, many: string): StatItem => ({
    kind,
    value: count.toLocaleString('en-US'),
    label: count === 1 ? one : many,
  })
  return [
    item('programs', counts.documents, 'program', 'programs'),
    item('operations', counts.observations, 'operation', 'operations'),
    assemblies === undefined
      ? item('cutters', counts.cutters, 'cutter', 'cutters')
      : item('assemblies', assemblies, 'assembly', 'assemblies'),
  ]
}

/** The same figures as one sentence: "3 programs, 118 operations, 22 cutters". */
export function countsSummary(counts: Counts, assemblies?: number): string {
  return statItems(counts, assemblies)
    .map((item) => `${item.value} ${item.label}`)
    .join(', ')
}

/** The saved database a typed name would overwrite: Windows file names
 *  ignore capitals, and the spaces around a name are dropped. */
export function findSaved(databases: SavedDatabase[], name: string): SavedDatabase | undefined {
  const wanted = name.trim().toLowerCase()
  return databases.find((database) => database.name.toLowerCase() === wanted)
}

/** What a saved database holds, for its row in the list. */
export function savedSummary(database: SavedDatabase): string {
  return database.counts === null ? 'Cannot be read' : countsSummary(database.counts)
}

const FIELD_ROWS: { key: string; label: string; kind: 'length' | 'angle' | 'count' | 'text' }[] = [
  { key: 'DC', label: 'Diameter', kind: 'length' },
  { key: 'NOF', label: 'Flutes', kind: 'count' },
  { key: 'LCF', label: 'Flute length', kind: 'length' },
  { key: 'shoulder-length', label: 'Shoulder length', kind: 'length' },
  { key: 'OAL', label: 'Overall length', kind: 'length' },
  { key: 'SFDM', label: 'Shaft diameter', kind: 'length' },
  { key: 'RE', label: 'Corner radius', kind: 'length' },
  { key: 'tip-diameter', label: 'Tip diameter', kind: 'length' },
  { key: 'TP', label: 'Thread pitch', kind: 'length' },
  { key: 'TA', label: 'Taper angle', kind: 'angle' },
  { key: 'SIG', label: 'Tip angle', kind: 'angle' },
  { key: 'material', label: 'Material', kind: 'text' },
]

/** One line of a cutter's geometry. `other` is a length in the other unit (see LengthParts), '' otherwise. */
export interface FieldRow {
  label: string
  value: string
  other: string
}

/** A cutter's geometry as labelled lines, in a fixed order. Fields the cutter does not have are left out. */
export function cutterFieldRows(fields: CutterFields, units: string[], display: LengthUnit): FieldRow[] {
  const both = enteredInOtherUnit(units, display)
  const rows: FieldRow[] = []
  for (const { key, label, kind } of FIELD_ROWS) {
    const value = fields[key]
    if (value === undefined || value === '') continue
    if (kind === 'text') rows.push({ label, value: String(value), other: '' })
    else if (typeof value !== 'number') continue
    else if (kind === 'length') {
      const parts = lengthParts(value, value, display, both, true)
      rows.push({ label, value: parts.shown, other: parts.other })
    } else if (kind === 'angle') rows.push({ label, value: `${Number(value.toFixed(3))}°`, other: '' })
    else rows.push({ label, value: String(value), other: '' })
  }
  return rows
}

/** One line of a cutter's speeds and feeds. `mostUsed` is '' when there is none. */
export interface SpeedRow {
  label: string
  range: string
  mostUsed: string
}

function feedInUnit(mmPerMin: number, display: LengthUnit): string {
  return display === 'in'
    ? (mmPerMin / MM_PER_INCH).toFixed(1)
    : Math.round(mmPerMin).toLocaleString('en-US')
}

/**
 * The spindle speeds and feeds a cutter ran at: the range, and the value most
 * operations used. Feeds are shown per minute in the chosen unit. A line is
 * left out when no operation has a number for it.
 */
export function speedRows(speeds: Speeds, display: LengthUnit): SpeedRow[] {
  const rows: SpeedRow[] = []
  const add = (label: string, spread: Speeds['spindle_rpm'], unit: string, text: (value: number) => string) => {
    if (spread === null) return
    const range = spread.min === spread.max ? text(spread.min) : `${text(spread.min)}–${text(spread.max)}`
    rows.push({
      label,
      range: `${range} ${unit}`,
      mostUsed: spread.most_used === null ? '' : `${text(spread.most_used)} ${unit}`,
    })
  }
  add('Spindle speed', speeds.spindle_rpm, 'rpm', (rpm) => Math.round(rpm).toLocaleString('en-US'))
  add('Feed', speeds.feed_mm_min, `${display}/min`, (feed) => feedInUnit(feed, display))
  return rows
}

/** What to say about operations that have no speed or feed number; '' when all have. */
export function speedsNote(speeds: Speeds): string {
  const without = speeds.operations_without
  if (without === 0) return ''
  if (speeds.spindle_rpm === null && speeds.feed_mm_min === null) {
    return 'None recorded. Scan the programs again to read them.'
  }
  return `${plural(without, 'operation')} ${without === 1 ? 'has' : 'have'} none recorded.`
}

/** One tally line as the holding library is told about it. */
export interface LibraryLine {
  cutterKey: string
  assemblyKey: string | null // set when counting by assembly
}

export function libraryLine(row: TallyRow): LibraryLine {
  return { cutterKey: row.cutter_key, assemblyKey: row.assembly_key ?? null }
}

/**
 * How many of the cutters in the list as shown are ticked: what the box in
 * the heading shows. It counts cutters, not lines: counting by assembly, a
 * cutter has several lines and only one of them carries its tick. `rows` is
 * the whole tally, since that line may be filtered out of `shown`.
 */
export function tickedState(shown: TallyRow[], rows: TallyRow[]): 'all' | 'some' | 'none' {
  const ticked = new Set(rows.filter((row) => row.in_library).map((row) => row.cutter_key))
  const cutters = new Set(shown.map((row) => row.cutter_key))
  let count = 0
  cutters.forEach((key) => {
    if (ticked.has(key)) count += 1
  })
  if (count === 0) return 'none'
  return count === cutters.size ? 'all' : 'some'
}

/**
 * The lines from the one clicked before (`fromKey`, a rowKey) to the one
 * clicked now, in the order shown, both included: a shift-click's run. Just
 * the clicked line when the earlier one is no longer in the list.
 */
export function rowsBetween(shown: TallyRow[], fromKey: string | null, toKey: string): TallyRow[] {
  const to = shown.findIndex((row) => rowKey(row) === toKey)
  if (to < 0) return []
  const from = fromKey === null ? -1 : shown.findIndex((row) => rowKey(row) === fromKey)
  if (from < 0) return [shown[to]]
  return shown.slice(Math.min(from, to), Math.max(from, to) + 1)
}

export interface LibraryOption {
  value: string // an assembly's key; '' for "whichever is usual"
  label: string
}

/**
 * The holders and stickouts a cutter can be written to the holding library
 * in. The first leaves the choice to ToolGuru and says what that comes to:
 * the usual setup, or the most recently used one when none is usual.
 */
export function libraryOptions(detail: CutterDetail, display: LengthUnit): LibraryOption[] {
  const label = (assembly: DetailAssembly): string => assemblyLabel(assembly, detail.units, display)
  const automatic = detail.assemblies.find((assembly) => assembly.assembly_key === detail.library.assembly_key)
  const how = detail.usual.assembly_key === null ? 'Most recently used' : 'Usual setup'
  const picksItself = detail.library.choice === null && automatic !== undefined
  return [
    { value: '', label: picksItself ? `${how}: ${label(automatic)}` : how },
    ...detail.assemblies.map((assembly) => ({ value: assembly.assembly_key, label: label(assembly) })),
  ]
}

/** The write button's text: "Write holding library (12)". */
export function writeLibraryLabel(count: number): string {
  return count === 0 ? 'Write holding library' : `Write holding library (${count})`
}

/** The "# Merged" figure of a tally line: blank for a cutter that stands only for itself. */
export function mergedCount(merged: number): string {
  return merged > 1 ? String(merged) : ''
}

/** A similar group in a line: "flat end mill · 3 cutters · 148 operations". */
export function groupSummary(group: SimilarGroup): string {
  const operations = group.members.reduce((sum, member) => sum + member.operations, 0)
  return `${group.tool_type} · ${plural(group.members.length, 'cutter')} · ${plural(operations, 'operation')}`
}

function fieldRow(key: string): (typeof FIELD_ROWS)[number] | undefined {
  return FIELD_ROWS.find((row) => row.key === key)
}

/** Headings for the fields a group differs in; a length names the unit it is shown in. */
export function variantHeadings(differs: string[], display: LengthUnit): string[] {
  return differs.map((key) => {
    const row = fieldRow(key)
    if (row === undefined) return key
    return row.kind === 'length' ? unitHeading(row.label, display) : row.label
  })
}

export interface VariantCell {
  text: string
  differs: boolean // not the same as the most used cutter's
}

/**
 * One cutter's values for the fields its group differs in, each marked when
 * it is not what the most used cutter (`first`) has. A field the cutter was
 * entered without reads "blank".
 */
export function variantCells(
  member: SimilarMember,
  first: SimilarMember,
  differs: string[],
  display: LengthUnit,
): VariantCell[] {
  return differs.map((key) => {
    const value = member.fields[key]
    const kind = fieldRow(key)?.kind
    let text = 'blank'
    if (typeof value === 'number') {
      text = kind === 'length' ? inUnit(value, display) : kind === 'angle' ? `${Number(value.toFixed(3))}°` : String(value)
    } else if (typeof value === 'string' && value !== '') {
      text = value
    }
    return { text, differs: value !== first.fields[key] }
  })
}

const M_PER_FOOT = 0.3048
const NO_VALUE = '—'

/** The headings of the cutting-data numbers, naming the unit each is shown in. */
export function presetHeadings(display: LengthUnit): string[] {
  return [
    'rpm',
    `Feed(${display}/min)`,
    display === 'in' ? 'SFM' : 'm/min',
    unitHeading('Chip load', display),
    `Plunge(${display}/min)`,
    `Ramp(${display}/min)`,
    'Ramp rpm',
    unitHeading('Stepover', display),
    unitHeading('Stepdown', display),
  ]
}

/**
 * One preset's numbers as text, in the order of `presetHeadings`. Surface
 * speed is in feet or metres per minute; chip load has one more decimal
 * place than other lengths, since it is that much smaller.
 */
export function presetValues(preset: DetailPreset, display: LengthUnit): string[] {
  const inch = display === 'in'
  const show = (value: number | null, text: (value: number) => string): string =>
    value === null ? NO_VALUE : text(value)
  const whole = (value: number): string => Math.round(value).toLocaleString('en-US')
  const feed = (value: number): string => feedInUnit(value, display)
  const length = (value: number): string => inUnit(value, display)
  return [
    show(preset.spindle_rpm, whole),
    show(preset.feed_mm_min, feed),
    show(preset.surface_m_min, (value) => whole(inch ? value / M_PER_FOOT : value)),
    show(preset.chip_load_mm, (value) => (inch ? (value / MM_PER_INCH).toFixed(4) : value.toFixed(3))),
    show(preset.plunge_mm_min, feed),
    show(preset.ramp_mm_min, feed),
    show(preset.ramp_rpm, whole),
    show(preset.stepover_mm, length),
    show(preset.stepdown_mm, length),
  ]
}

/** What tells two lines of the list apart: the name and every number. */
export function presetKey(preset: DetailPreset): string {
  return [
    preset.name,
    preset.spindle_rpm,
    preset.feed_mm_min,
    preset.chip_load_mm,
    preset.surface_m_min,
    preset.plunge_mm_min,
    preset.ramp_mm_min,
    preset.ramp_rpm,
    preset.stepover_mm,
    preset.stepdown_mm,
  ].join('|')
}

/** "flat end mill · carbide". A material Fusion left unspecified is not shown. */
export function cutterSubtitle(cutter: { tool_type: string; fields: CutterFields }): string {
  const material = cutter.fields.material
  const known = typeof material === 'string' && material !== '' && material !== 'unspecified'
  return known ? `${cutter.tool_type} · ${material}` : cutter.tool_type
}

/** "Test Holder, 1.500 in": one holder and stickout a cutter ran in. */
export function assemblyLabel(assembly: DetailAssembly, units: string[], display: LengthUnit): string {
  const holder = assembly.holder || 'no holder'
  if (assembly.stickout_min_mm === null) return holder
  return `${holder}, ${formatStickout(assembly.stickout_min_mm, assembly.stickout_max_mm, units, display)}`
}

/** Same column flips direction; a new column starts A–Z for text, largest first for numbers. */
export function toggleSort(current: SortState, key: SortKey): SortState {
  if (current.key === key) {
    return { key, direction: current.direction === 'asc' ? 'desc' : 'asc' }
  }
  return { key, direction: TEXT_KEYS.includes(key) ? 'asc' : 'desc' }
}

export function sortTally(rows: TallyRow[], sort: SortState): TallyRow[] {
  const sign = sort.direction === 'asc' ? 1 : -1
  return [...rows].sort((a, b) => {
    const left = a[sort.key]
    const right = b[sort.key]
    let order: number
    if (typeof left === 'string' && typeof right === 'string') {
      order = left.localeCompare(right)
    } else {
      // A cutter with no diameter sorts as the smallest.
      order = ((left as number | null) ?? -Infinity) - ((right as number | null) ?? -Infinity)
    }
    if (order !== 0 && !Number.isNaN(order)) return sign * order
    return rowKey(a).localeCompare(rowKey(b))
  })
}

// What the tally's drop-down narrows the list to: 'all', one family
// ('family:milling') or one tool type ('type:drill').

export function familyChoice(family: string): string {
  return `family:${family}`
}

export function typeChoice(toolType: string): string {
  return `type:${toolType}`
}

function matchesChoice(row: TallyRow, choice: string): boolean {
  return choice === 'all' || choice === familyChoice(row.family) || choice === typeChoice(row.tool_type)
}

/** `choice`, or 'all' when no row matches it any more: the data changed under the drop-down. */
export function validChoice(rows: TallyRow[], choice: string): string {
  return rows.some((row) => matchesChoice(row, choice)) ? choice : 'all'
}

/** `choice` is a drop-down choice (see above). Text matches description, type, holder, or a tool number (7 or T7). */
export function filterTally(rows: TallyRow[], text: string, choice: string): TallyRow[] {
  const needle = text.trim().toLowerCase()
  return rows.filter((row) => {
    if (!matchesChoice(row, choice)) return false
    if (needle === '') return true
    const haystack = [
      row.description,
      row.tool_type,
      row.holder ?? '',
      ...row.tool_numbers.flatMap((n) => [String(n), `t${n}`]),
    ]
    return haystack.some((value) => value.toLowerCase().includes(needle))
  })
}

export function familiesIn(rows: TallyRow[]): string[] {
  return [...new Set(rows.map((row) => row.family))].sort()
}

// The families whose tool types are offered one by one in the drop-down.
const FAMILIES_BY_TYPE = ['milling', 'hole making']

/**
 * The milling and hole making tool types found in `rows`, A to Z within each
 * family. Only what the scans found is listed, so a type Fusion offers but no
 * program used never appears, and a family with nothing found is left out.
 */
export function typesByFamily(rows: TallyRow[]): { family: string; types: string[] }[] {
  return FAMILIES_BY_TYPE.map((family) => ({
    family,
    types: [...new Set(rows.filter((row) => row.family === family).map((row) => row.tool_type))].sort(),
  })).filter((group) => group.types.length > 0)
}

/** How narrow and how wide the description column may be, in pixels. */
export const DESCRIPTION_WIDTH = { min: 80, max: 1000 }

/** A width for the description column: a whole number of pixels inside its limits. */
export function clampWidth(px: number): number {
  return Math.min(DESCRIPTION_WIDTH.max, Math.max(DESCRIPTION_WIDTH.min, Math.round(px)))
}

/** The column's width after its edge is dragged `moved` pixels from where it was `start` wide. */
export function draggedWidth(start: number, moved: number): number {
  return clampWidth(start + moved)
}

/** How far a folder scan has got, 0 to 100. An empty scan is complete. */
export function scanPercent(scan: ScanJob): number {
  if (scan.total === 0) return 100
  return Math.round(((scan.total - scan.pending) / scan.total) * 100)
}

/** "Scanning “Folder”: 12 of 40", or paused / finished. */
export function scanHeadline(scan: ScanJob): string {
  const progress = `${scan.total - scan.pending} of ${scan.total}`
  if (scan.running) return `Scanning “${scan.folder}”: ${progress}`
  if (scan.pending > 0) return `Scan of “${scan.folder}” paused at ${progress}`
  return `Scan of “${scan.folder}” finished: ${progress}`
}

/** "10 scanned, 1 skipped, 1 failed", naming unchanged programs only when there are some. */
export function scanOutcome(scan: ScanJob): string {
  const unchanged = scan.unchanged > 0 ? `${scan.unchanged} unchanged, ` : ''
  return `${scan.scanned} scanned, ${unchanged}${scan.skipped} skipped, ${scan.failed} failed`
}

/**
 * What a counted folder holds and what a scan of it would do. Programs that
 * have not been saved since they were scanned are not opened again.
 */
export function confirmScanText(confirm: ConfirmScan): string {
  const holds = `“${confirm.folder}” contains ${plural(confirm.count, 'Fusion design')}.`
  const opened = confirm.count - confirm.unchanged
  if (opened === 0) {
    return `${holds} None has changed since it was scanned, so a scan would open nothing.`
  }
  if (confirm.unchanged === 0) {
    return `${holds} Scan ${confirm.count === 1 ? 'it' : 'them'}? Each one is opened, read and closed without saving.`
  }
  return (
    `${holds} ${confirm.unchanged} ${confirm.unchanged === 1 ? 'has' : 'have'} not changed since ` +
    `${confirm.unchanged === 1 ? 'it was' : 'they were'} scanned and will be skipped. Scan the other ${opened}? ` +
    'Each one is opened, read and closed without saving.'
  )
}

/** What the folder picker says about the level it is showing. */
export function browserHere(browser: Browser): string {
  if (browser.folderId === '') return 'Choose a project.'
  return `${plural(browser.programs, 'Fusion design')} directly in this folder.`
}
