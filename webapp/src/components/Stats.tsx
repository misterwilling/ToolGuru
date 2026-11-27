import type { ReactNode } from 'react'
import type { Counts } from '../types'
import { statItems } from '../utils'
import type { StatKind } from '../utils'

// Small line drawings, in the text colour they are given. Drawn here, so the
// palette needs no icon library and nothing from the network.
function Icon({ children }: { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 16 16"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  )
}

const ICONS: Record<StatKind, ReactNode> = {
  // A page with a folded corner: a program.
  programs: (
    <Icon>
      <path d="M4 1.5h5.5L12.5 4.5v10H4z" />
      <path d="M9.5 1.5v3h3" />
      <path d="M6.2 8h4.1M6.2 10.5h4.1" />
    </Icon>
  ),
  // A toolpath: back-and-forth passes from a start point to an arrowhead.
  operations: (
    <Icon>
      <path d="M3.2 3.2h7.6a2.3 2.3 0 0 1 0 4.6H5.2a2.3 2.3 0 0 0 0 4.6h7.4" />
      <path d="M10.7 10.4l2.1 2-2.1 2" />
      <circle cx="3.2" cy="3.2" r="1.3" fill="currentColor" stroke="none" />
    </Icon>
  ),
  // An end mill: a plain shank over flutes that spiral down to a flat end.
  cutters: (
    <Icon>
      <path d="M5.5 14.5V2.3a.8.8 0 0 1 .8-.8h3.4a.8.8 0 0 1 .8.8v12.2z" />
      <path d="M5.5 8.5l5-3v3l-5 3z" fill="currentColor" fillOpacity="0.45" />
      <path d="M5.5 14.5l5-3v3z" fill="currentColor" fillOpacity="0.45" />
    </Icon>
  ),
  // A tapered holder with a cutter in it: an assembly.
  assemblies: (
    <Icon>
      <path d="M3.5 1.5h9l-1.8 4.6H5.3z" />
      <path d="M5.9 6.1h4.2v2.6H5.9z" />
      <path d="M7 8.7h2v5.8H7z" />
    </Icon>
  ),
}

interface Props {
  counts: Counts
  /** How many assemblies the list shows, when counting by assembly. */
  assemblies?: number
}

/** What has been scanned, as a row of figures: programs, operations, and cutters or assemblies. */
export function Stats({ counts, assemblies }: Props) {
  return (
    <div className="stats">
      {statItems(counts, assemblies).map((item) => (
        <span key={item.kind} className="stat">
          {ICONS[item.kind]}
          <b>{item.value}</b> {item.label}
        </span>
      ))}
    </div>
  )
}
