import { useEffect, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import type { CountBy, LengthUnit, SortKey, SortState, TallyRow } from '../types'
import {
  clampWidth,
  diameterParts,
  draggedWidth,
  familiesIn,
  familyChoice,
  filterTally,
  formatDate,
  formatDuration,
  formatToolNumbers,
  otherUnit,
  rowKey,
  sortTally,
  stickoutParts,
  toggleSort,
  typeChoice,
  unitHeading,
  typesByFamily,
  validChoice,
} from '../utils'

const BEFORE_DIAMETER: Column[] = [{ key: 'tool_type', label: 'Type', numeric: false }]
const AFTER_DIAMETER: Column[] = [
  { key: 'flutes', label: 'Flutes', numeric: true },
  { key: 'description', label: 'Description', numeric: false },
  { key: 'programs', label: 'PGMs', numeric: true, hint: 'Programs that used the tool' },
  { key: 'operations', label: 'OPs', numeric: true, hint: 'Operations that used the tool' },
  { key: 'time_s', label: 'Cutting time', numeric: true },
  { key: 'first_used', label: 'First used', numeric: true },
  { key: 'last_used', label: 'Last used', numeric: true },
]

interface Column {
  key: SortKey
  label: string
  numeric: boolean
  /** Shown when the pointer rests on a shortened heading. */
  hint?: string
}

interface Props {
  rows: TallyRow[]
  countBy: CountBy
  display: LengthUnit
  /** The remembered width of the description column, in pixels. */
  descriptionWidth: number
  /** The user finished dragging the description column to this width. */
  onResized: (widthPx: number) => void
  /** Open the detail of the cutter in the clicked row. */
  onOpen: (cutterKey: string) => void
}

export function TallyTable({ rows, countBy, display, descriptionWidth, onResized, onOpen }: Props) {
  const [sort, setSort] = useState<SortState>({ key: 'operations', direction: 'desc' })
  const [text, setText] = useState('')
  const [picked, setPicked] = useState('all')
  // The description column keeps a set width, so one long description cannot
  // stretch the whole list. Dragging the handle on its heading changes it;
  // the width follows the pointer here and is saved when the drag ends.
  const [width, setWidth] = useState(clampWidth(descriptionWidth))
  useEffect(() => setWidth(clampWidth(descriptionWidth)), [descriptionWidth])
  // `width` in the drag is where the pointer has taken it: the state above
  // may not have caught up when the button is released.
  const drag = useRef<{ startX: number; startWidth: number; width: number } | null>(null)
  const endDrag = () => {
    const ended = drag.current
    if (ended && ended.width !== ended.startWidth) onResized(ended.width)
    drag.current = null
  }

  const byAssembly = countBy === 'assembly'
  // The drop-down lists only what is in the data, so a choice can vanish
  // when the data changes: after a rescan or a reset.
  const choice = validChoice(rows, picked)
  const shown = sortTally(filterTally(rows, text, choice), sort).map((row) => ({
    row,
    diameter: diameterParts(row.diameter_mm, row.units, display),
    stickout: stickoutParts(row.stickout_min_mm, row.stickout_max_mm, row.units, display),
  }))
  // A length keeps its own column, so every row's value lines up. The other
  // unit, shown for tools entered in it, gets a column of its own beside it,
  // and only when some row has one.
  const otherDiameters = shown.some((line) => line.diameter.other !== '')
  const otherStickouts = byAssembly && shown.some((line) => line.stickout.other !== '')
  // Each length column names its unit once, in its heading; the rows under
  // it are bare figures.
  const other = otherUnit(display)
  const diameter: Column = {
    key: 'diameter_mm',
    label: unitHeading('Dia', display),
    numeric: true,
    hint: `Diameter in ${display === 'in' ? 'inches' : 'millimetres'}`,
  }

  const heading = (column: Column) => (
    <th
      key={column.key}
      className={column.numeric ? 'num' : undefined}
      title={column.hint}
      onClick={() => setSort(toggleSort(sort, column.key))}
    >
      {column.label}
      {sort.key === column.key ? (sort.direction === 'asc' ? ' ▲' : ' ▼') : ''}
      {column.key === 'description' && (
        <span
          className="resizer"
          title="Drag to make this column wider or narrower"
          // A drag ends in a click; it must not also sort the column.
          onClick={(event) => event.stopPropagation()}
          onPointerDown={(event) => {
            event.currentTarget.setPointerCapture(event.pointerId)
            drag.current = { startX: event.clientX, startWidth: width, width }
          }}
          onPointerMove={(event) => {
            const from = drag.current
            if (!from) return
            from.width = draggedWidth(from.startWidth, event.clientX - from.startX)
            setWidth(from.width)
          }}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
        />
      )}
    </th>
  )

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
        <select value={choice} onChange={(event) => setPicked(event.target.value)}>
          <option value="all">All families</option>
          {familiesIn(rows).map((name) => (
            <option key={name} value={familyChoice(name)}>{name}</option>
          ))}
          {typesByFamily(rows).map((group) => (
            <optgroup key={group.family} label={`${group.family} tool types`}>
              {group.types.map((toolType) => (
                <option key={toolType} value={typeChoice(toolType)}>{toolType}</option>
              ))}
            </optgroup>
          ))}
        </select>
        <span className="muted">
          {shown.length} of {rows.length} {byAssembly ? 'assemblies' : 'cutters'}. Click a row for the
          cutter's detail.
        </span>
      </div>
      <table style={{ '--description-width': `${width}px` } as CSSProperties}>
        <thead>
          <tr>
            {BEFORE_DIAMETER.map(heading)}
            {heading(diameter)}
            {otherDiameters && (
              <th className="other" onClick={() => setSort(toggleSort(sort, diameter.key))}>
                {unitHeading('Dia', other)}
              </th>
            )}
            {AFTER_DIAMETER.map(heading)}
            {byAssembly && <th>Holder</th>}
            {byAssembly && <th className="num">{unitHeading('Stickout', display)}</th>}
            {otherStickouts && <th className="other">{unitHeading('Stickout', other)}</th>}
            <th>Tool numbers</th>
            <th>Machines</th>
          </tr>
        </thead>
        <tbody>
          {shown.map(({ row, diameter: dia, stickout }) => (
            <tr key={rowKey(row)} className="clickable" onClick={() => onOpen(row.cutter_key)}>
              <td>{row.tool_type}</td>
              <td className="num main">{dia.shown}</td>
              {otherDiameters && <td className="other">{dia.other}</td>}
              <td className="num">{row.flutes ?? ''}</td>
              <td>
                <div className="clip" title={row.description}>
                  {row.merged > 1 && (
                    <span className="tag lead" title="Similar cutters you chose to treat as the same">
                      {row.merged} merged
                    </span>
                  )}
                  {row.description}
                </div>
              </td>
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
              {byAssembly && <td className="num">{stickout.shown}</td>}
              {otherStickouts && <td className="other">{stickout.other}</td>}
              <td>{formatToolNumbers(row.tool_numbers)}</td>
              <td>{row.machines.join(', ')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
