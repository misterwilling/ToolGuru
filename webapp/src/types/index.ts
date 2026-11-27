/** 'cutter': same cutter geometry is one tool. 'assembly': holder and stickout count too. */
export type CountBy = 'cutter' | 'assembly'

export type LengthUnit = 'in' | 'mm'

export type Theme = 'light' | 'dark'

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

/** How widely a cutter was used with one value: a tool number, a machine, a name. */
export interface Use<T> {
  value: T
  programs: number
  operations: number
}

/** One holder and stickout a cutter was used in. */
export interface DetailAssembly {
  assembly_key: string
  holder: string
  stickout_min_mm: number | null
  stickout_max_mm: number | null
  programs: number
  operations: number
  time_s: number
}

/** A value a program used, and whether it is the cutter's usual one. */
export interface Marked<T> {
  value: T
  usual: boolean
}

/** One holder and stickout a program ran a cutter in, compared with the cutter's usual assembly. */
export interface ProgramSetup {
  holder: string
  holder_usual: boolean
  stickout_min_mm: number | null
  stickout_max_mm: number | null
  stickout_usual: boolean
  operations: number
}

/** One program that used a cutter. */
export interface DetailProgram {
  file_id: string
  name: string
  last_saved: number // UNIX epoch seconds
  operations: number
  time_s: number
  tool_numbers: Marked<number>[]
  machines: Marked<string>[]
  setups: ProgramSetup[] // most operations first
}

/** Cutter geometry in millimetres and degrees, keyed by Fusion's own names, plus `material`. */
export type CutterFields = Record<string, number | string>

/**
 * The tally row of one cutter plus its geometry, its usual setup and its
 * programs. `usual` names the tool number, machine and assembly most
 * programs used; each is null when the top two were used equally.
 */
export interface CutterDetail extends TallyRow {
  fields: CutterFields
  usual: { tool_number: number | null; machine: string | null; assembly_key: string | null }
  tool_number_use: Use<number>[]
  machine_use: Use<string>[]
  assemblies: DetailAssembly[]
  program_list: DetailProgram[]
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
  counts: Counts
  countBy: CountBy
  stickoutToleranceMm: number
  displayUnit: LengthUnit // lengths are shown in this unit first
  descriptionWidthPx: number // where the user left the tally's description column
  theme?: Theme // Fusion's own light or dark setting
  toolPictures?: Record<string, string> // tool type -> address of Fusion's picture of it
  tally: TallyRow[]
  detail: CutterDetail | null // the cutter opened from the tally, if any
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
  | 'flutes'
  | 'programs'
  | 'operations'
  | 'time_s'
  | 'first_used'
  | 'last_used'

export interface SortState {
  key: SortKey
  direction: 'asc' | 'desc'
}
