// Pure utility functions — no React, no DOM, no bridge. Everything that
// doesn't need a browser goes here so it's directly testable with Vitest.

import type { AppState, Counts, Dataset, SortKey, SortState, TallyRow } from './types'

const MM_PER_INCH = 25.4
const TEXT_KEYS: SortKey[] = ['tool_type', 'description']

export function isAppState(value: unknown): value is AppState {
  return typeof value === 'object' && value !== null && 'dataset' in value && 'tally' in value
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

/** Millimetres always; inches as well when the cutter was ever entered in inches. */
export function formatDiameter(mm: number | null, units: string[]): string {
  if (mm === null) return '—'
  const metric = `${mm.toFixed(3)} mm`
  if (!units.includes('inches')) return metric
  return `${metric} / ${(mm / MM_PER_INCH).toFixed(4)} in`
}

export function formatDate(epochSeconds: number): string {
  const date = new Date(epochSeconds * 1000)
  const two = (n: number): string => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${two(date.getMonth() + 1)}-${two(date.getDate())}`
}

export function formatToolNumbers(numbers: number[]): string {
  return numbers.map((n) => `T${n}`).join(', ')
}

export function datasetBadge(dataset: Dataset): { label: string; tone: Dataset } {
  return dataset === 'trial'
    ? { label: 'TRIAL DATA', tone: 'trial' }
    : { label: 'MAIN DATA', tone: 'main' }
}

function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? '' : 's'}`
}

export function countsSummary(counts: Counts): string {
  return [
    plural(counts.documents, 'program'),
    plural(counts.observations, 'operation'),
    plural(counts.cutters, 'cutter'),
  ].join(', ')
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
    return a.cutter_key.localeCompare(b.cutter_key)
  })
}

/** `family` is a family name or 'all'. Text matches description, type, or a tool number (7 or T7). */
export function filterTally(rows: TallyRow[], text: string, family: string): TallyRow[] {
  const needle = text.trim().toLowerCase()
  return rows.filter((row) => {
    if (family !== 'all' && row.family !== family) return false
    if (needle === '') return true
    const haystack = [
      row.description,
      row.tool_type,
      ...row.tool_numbers.flatMap((n) => [String(n), `t${n}`]),
    ]
    return haystack.some((value) => value.toLowerCase().includes(needle))
  })
}

export function familiesIn(rows: TallyRow[]): string[] {
  return [...new Set(rows.map((row) => row.family))].sort()
}
