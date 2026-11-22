import { useState } from 'react'
import type { CountBy, SortKey, SortState, TallyRow } from '../types'
import {
  familiesIn,
  filterTally,
  formatDate,
  formatDiameter,
  formatDuration,
  formatStickout,
  formatToolNumbers,
  rowKey,
  sortTally,
  toggleSort,
} from '../utils'

const COLUMNS: { key: SortKey; label: string; numeric: boolean }[] = [
  { key: 'tool_type', label: 'Type', numeric: false },
  { key: 'diameter_mm', label: 'Diameter', numeric: true },
  { key: 'description', label: 'Description', numeric: false },
  { key: 'programs', label: 'Programs', numeric: true },
  { key: 'operations', label: 'Operations', numeric: true },
  { key: 'time_s', label: 'Cutting time', numeric: true },
  { key: 'first_used', label: 'First used', numeric: true },
  { key: 'last_used', label: 'Last used', numeric: true },
]

export function TallyTable({ rows, countBy }: { rows: TallyRow[]; countBy: CountBy }) {
  const [sort, setSort] = useState<SortState>({ key: 'operations', direction: 'desc' })
  const [text, setText] = useState('')
  const [family, setFamily] = useState('all')

  const byAssembly = countBy === 'assembly'
  const shown = sortTally(filterTally(rows, text, family), sort)

  return (
    <section>
      <div className="filters">
        <input
          type="search"
          placeholder={
            byAssembly
              ? 'Filter by description, type, holder or tool number'
              : 'Filter by description, type or tool number'
          }
          value={text}
          onChange={(event) => setText(event.target.value)}
        />
        <select value={family} onChange={(event) => setFamily(event.target.value)}>
          <option value="all">All families</option>
          {familiesIn(rows).map((name) => (
            <option key={name} value={name}>{name}</option>
          ))}
        </select>
        <span className="muted">
          {shown.length} of {rows.length} {byAssembly ? 'assemblies' : 'cutters'}
        </span>
      </div>
      <table>
        <thead>
          <tr>
            {COLUMNS.map((column) => (
              <th
                key={column.key}
                className={column.numeric ? 'num' : undefined}
                onClick={() => setSort(toggleSort(sort, column.key))}
              >
                {column.label}
                {sort.key === column.key ? (sort.direction === 'asc' ? ' ▲' : ' ▼') : ''}
              </th>
            ))}
            {byAssembly && <th>Holder</th>}
            {byAssembly && <th className="num">Stickout</th>}
            <th>Tool numbers</th>
            <th>Machines</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((row) => (
            <tr key={rowKey(row)}>
              <td>{row.tool_type}</td>
              <td className="num">
                {formatDiameter(row.diameter_mm, row.units)}
                {row.flutes ? ` · ${row.flutes}fl` : ''}
              </td>
              <td>{row.description}</td>
              <td className="num">{row.programs}</td>
              <td className="num">{row.operations}</td>
              <td className="num">
                {formatDuration(row.time_s)}
                {row.operations_without_time > 0 && (
                  <span className="muted" title="Operations with no saved cutting time">
                    {' '}(+{row.operations_without_time} no time)
                  </span>
                )}
              </td>
              <td className="num">{formatDate(row.first_used)}</td>
              <td className="num">{formatDate(row.last_used)}</td>
              {byAssembly && <td>{row.holder || <span className="muted">no holder</span>}</td>}
              {byAssembly && (
                <td className="num">
                  {formatStickout(row.stickout_min_mm, row.stickout_max_mm, row.units)}
                </td>
              )}
              <td>{formatToolNumbers(row.tool_numbers)}</td>
              <td>{row.machines.join(', ')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
