export type Dataset = 'trial' | 'main'

/** 'cutter': same cutter geometry is one tool. 'assembly': holder and stickout count too. */
export type CountBy = 'cutter' | 'assembly'

export type LengthUnit = 'in' | 'mm'

export interface TallyRow {
  cutter_key: string
  tool_type: string
  family: string
  description: string
  diameter_mm: number | null
  flutes: number | null
  programs: number
  operations: number
  time_s: number
  operations_without_time: number
  first_used: number // UNIX epoch seconds
  last_used: number // UNIX epoch seconds
  tool_numbers: number[]
  machines: string[]
  units: string[]
  // Present only when counting by assembly.
  assembly_key?: string
  holder?: string
  stickout_min_mm?: number | null
  stickout_max_mm?: number | null
}

export interface Counts {
  documents: number
  observations: number
  cutters: number
}

export interface LastScan {
  name: string
  operations: number
  cutters: number
  operationsWithoutTime: number
}

export interface FolderEntry {
  id: string
  name: string
}

/** One level of the hub in the folder picker. An empty folderId is the list of projects. */
export interface Browser {
  folderId: string
  path: FolderEntry[]
  folders: FolderEntry[]
  programs: number // Fusion designs directly inside this folder
}

export interface ConfirmScan {
  folder: string
  count: number
}

export interface ScanProblem {
  name: string
  status: 'skipped' | 'failed'
  message: string
}

/** A folder scan's progress. total = pending + scanned + skipped + failed. */
export interface ScanJob {
  folder: string
  total: number
  pending: number
  scanned: number
  skipped: number
  failed: number
  problems: ScanProblem[]
  running: boolean
}

export interface AppState {
  dataset: Dataset
  counts: Counts
  countBy: CountBy
  stickoutToleranceMm: number
  tally: TallyRow[]
  lastScan: LastScan | null
  browser: Browser | null
  confirmScan: ConfirmScan | null
  scan: ScanJob | null
  notice: string
  error: string
}

export type SortKey =
  | 'tool_type'
  | 'description'
  | 'diameter_mm'
  | 'programs'
  | 'operations'
  | 'time_s'
  | 'first_used'
  | 'last_used'

export interface SortState {
  key: SortKey
  direction: 'asc' | 'desc'
}
