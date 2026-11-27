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
  in_library: boolean // ticked for the holding library
  merged: number // scanned cutters this line stands for; more than 1 after "treat as same"
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
  presets: { name: string; changed: boolean }[]
  setups: ProgramSetup[] // most operations first
}

/** Cutter geometry in millimetres and degrees, keyed by Fusion's own names, plus `material`. */
export type CutterFields = Record<string, number | string>

/**
 * The tally row of one cutter plus its geometry, its usual setup and its
 * programs. `usual` names the tool number, machine and assembly most
 * programs used; each is null when the top two were used equally.
 */
/** The lowest, highest and most often used value of a speed or feed. */
export interface Spread {
  min: number
  max: number
  most_used: number | null // null when the top two were used equally often
  operations: number
}

/** What a cutter ran at. A spread is null when no operation has a number. */
export interface Speeds {
  spindle_rpm: Spread | null
  feed_mm_min: Spread | null
  operations_without: number // scanned before the numbers were recorded, or never set
}

/**
 * One preset (Fusion's name for a tool's cutting data) that operations
 * picked. Numbers are in millimetres, mm/min, m/min and rpm; null when the
 * preset has none.
 */
export interface DetailPreset {
  name: string
  spindle_rpm: number | null
  feed_mm_min: number | null
  chip_load_mm: number | null
  surface_m_min: number | null
  plunge_mm_min: number | null
  ramp_mm_min: number | null
  ramp_rpm: number | null
  stepover_mm: number | null
  stepdown_mm: number | null
  programs: number
  operations: number
  changed: number // operations run at a different speed or feed
  unchecked: number // operations where that cannot be told
}

/** One scanned cutter in a group of similar ones, with its own usage. */
export interface SimilarMember {
  cutter_key: string
  description: string
  fields: CutterFields
  programs: number
  operations: number
  time_s: number
  merged?: boolean // in a suggestion: already treated as the same as another
}

/** Cutters shown side by side, most used first. `differs` names the fields that are not the same in all. */
export interface SimilarGroup {
  tool_type: string
  differs: string[]
  members: SimilarMember[]
  signature?: string // a suggestion's name, for "not the same"
  cutter_key?: string // a merged group's line in the tally
}

export interface SimilarView {
  suggestions: SimilarGroup[]
  merged: SimilarGroup[]
}

export interface CutterDetail extends TallyRow {
  fields: CutterFields
  variants: { differs: string[]; members: SimilarMember[] } | null // what a merged line was merged from
  /** Its place in the holding library: `choice` is the assembly picked for it (null: the usual one),
   *  `assembly_key` the one it is, or would be, written in. */
  library: { picked: boolean; choice: string | null; assembly_key: string }
  speeds: Speeds
  presets: DetailPreset[]
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

/** One saved database. `counts` is null when its file cannot be read. */
export interface SavedDatabase {
  name: string
  saved_at: number // epoch seconds
  counts: Counts | null
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
  databases: SavedDatabase[] | null // the saved databases, while their panel is open
  similar: SimilarView | null // the similar-cutters screen, while it is open
  libraryCount: number // cutters ticked for the holding library
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
  | 'merged'
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
