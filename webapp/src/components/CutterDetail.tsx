import type { ReactNode } from 'react'
import type { CutterDetail as Detail, LengthUnit } from '../types'
import { VariantTable } from './SimilarScreen'
import {
  assemblyLabel,
  cutterFieldRows,
  cutterSubtitle,
  formatDate,
  formatDuration,
  formatStickout,
  libraryOptions,
  presetHeadings,
  presetKey,
  presetValues,
  speedRows,
  speedsNote,
} from '../utils'

interface Props {
  detail: Detail
  display: LengthUnit
  /** Fusion's picture of this type of tool, when it has one. */
  picture?: string
  busy: boolean
  onClose: () => void
  /** Count the cutters this line was merged from apart again. */
  onSplit: () => void
  /** Put the cutter in the holding library, or take it out. `assemblyKey` null means its usual setup. */
  onPick: (picked: boolean, assemblyKey: string | null) => void
}

function Tile({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="tile">
      <span>{label}</span>
      <b>{children}</b>
    </div>
  )
}

interface UseRow {
  key: string
  label: string
  programs: number
  usual: boolean
}

/** One list of the usual setup: each value with the number of programs that used it, the usual one in bold. */
function UseList({ title, empty, rows }: { title: string; empty: string; rows: UseRow[] }) {
  const tied = rows.length > 1 && !rows.some((row) => row.usual)
  return (
    <table className="plain">
      <thead>
        <tr>
          <th colSpan={2}>
            {title}
            {tied && <span className="note"> — no usual one</span>}
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 && (
          <tr>
            <td colSpan={2} className="muted">{empty}</td>
          </tr>
        )}
        {rows.map((row) => (
          <tr key={row.key} className={row.usual ? 'usual' : undefined}>
            <td className="wrap">{row.label}</td>
            <td className="num">{row.programs}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/** A value in the compare table, marked when it is not the usual one. */
function Value({ usual, children }: { usual: boolean; children: ReactNode }) {
  return usual ? <>{children}</> : <span className="differs">{children}</span>
}

const NONE = <span className="muted">—</span>

/** One cutter: its figures, its geometry, its usual setup, and every program compared against that. */
export function CutterDetail({ detail, display, picture, busy, onClose, onSplit, onPick }: Props) {
  const geometry = cutterFieldRows(detail.fields, detail.units, display)
  const otherUnits = geometry.some((row) => row.other !== '')
  const speeds = speedRows(detail.speeds, display)
  const speedNote = speedsNote(detail.speeds)
  return (
    <section className="detail">
      <div className="actions">
        <button disabled={busy} onClick={onClose}>‹ Back to the tally</button>
      </div>

      <div className="summary">
        <div className="title">
          {picture && <img className="tool-picture" src={picture} alt="" />}
          <div>
            <h2>{detail.description || detail.tool_type}</h2>
            <p className="muted">{cutterSubtitle(detail)}</p>
          </div>
        </div>
        <div className="tiles">
          <Tile label="Programs">{detail.programs}</Tile>
          <Tile label="Operations">{detail.operations}</Tile>
          <Tile label="Cutting time">
            {formatDuration(detail.time_s)}
            {detail.operations_without_time > 0 && (
              <small title="Operations with no saved cutting time"> +{detail.operations_without_time} no time</small>
            )}
          </Tile>
          <Tile label="Last used">{formatDate(detail.last_used)}</Tile>
        </div>
      </div>

      <div className="actions library">
        {detail.library.writable ? (
          <label>
            <input
              type="checkbox"
              checked={detail.library.picked}
              disabled={busy}
              onChange={(event) => onPick(event.target.checked, null)}
            />{' '}
            Write to the holding library
          </label>
        ) : (
          <span className="muted">
            Read from Mastercam only. ToolGuru writes only tools scanned in Fusion to a Fusion tool library.
          </span>
        )}
        {detail.library.writable && detail.library.picked && (
          <>
            <span>with</span>
            <select
              value={detail.library.choice ?? ''}
              disabled={busy}
              onChange={(event) => onPick(true, event.target.value || null)}
            >
              {libraryOptions(detail, display).map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </>
        )}
      </div>

      <div className="columns">
        <div>
          <h3>Geometry</h3>
          <table className="plain">
            <tbody>
              {geometry.map((row) => (
                <tr key={row.label}>
                  <td>{row.label}</td>
                  <td className="num">{row.value}</td>
                  {otherUnits && <td className="other">{row.other}</td>}
                </tr>
              ))}
            </tbody>
          </table>

          <h3 className="after">Speeds and feeds</h3>
          {speeds.length > 0 && (
            <table className="plain">
              <thead>
                <tr>
                  <th />
                  <th className="num">Range</th>
                  <th className="num">Most used</th>
                </tr>
              </thead>
              <tbody>
                {speeds.map((row) => (
                  <tr key={row.label}>
                    <td>{row.label}</td>
                    <td className="num">{row.range}</td>
                    <td className="num">{row.mostUsed || NONE}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {speedNote && <p className="muted small">{speedNote}</p>}
        </div>
        <div>
          <h3>
            Usual setup <span className="note">— the bold line of each list. The numbers are programs.</span>
          </h3>
          <div className="three">
            <UseList
              title="Tool number"
              empty="None recorded"
              rows={detail.tool_number_use.map((use) => ({
                key: String(use.value),
                label: `T${use.value}`,
                programs: use.programs,
                usual: use.value === detail.usual.tool_number,
              }))}
            />
            <UseList
              title="Holder and stickout"
              empty="None recorded"
              rows={detail.assemblies.map((assembly) => ({
                key: assembly.assembly_key,
                label: assemblyLabel(assembly, detail.units, display),
                programs: assembly.programs,
                usual: assembly.assembly_key === detail.usual.assembly_key,
              }))}
            />
            <UseList
              title="Machine"
              empty="None set"
              rows={detail.machine_use.map((use) => ({
                key: use.value,
                label: use.value,
                programs: use.programs,
                usual: use.value === detail.usual.machine,
              }))}
            />
          </div>
        </div>
      </div>

      {detail.variants && (
        <>
          <h3>
            Merged from{' '}
            <span className="note">
              — similar cutters you chose to treat as the same. The first is the most used and names this line.
            </span>{' '}
            <button className="link" disabled={busy} onClick={onSplit}>Split</button>
          </h3>
          <div className="after">
            <VariantTable differs={detail.variants.differs} members={detail.variants.members} display={display} />
          </div>
        </>
      )}

      <h3>
        Cutting data{' '}
        <span className="note">
          — the presets operations picked. Changed counts the operations run at a different speed or feed.
        </span>
      </h3>
      {detail.presets.length === 0 ? (
        <p className="muted">None recorded.</p>
      ) : (
        <div className="scroll after">
          <table className="plain">
            <thead>
              <tr>
                <th>Preset</th>
                <th className="num" title="Programs that picked it">PGMs</th>
                <th className="num" title="Operations that picked it">OPs</th>
                <th className="num">Changed</th>
                {presetHeadings(display).map((heading) => (
                  <th key={heading} className="num">{heading}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {detail.presets.map((preset) => (
                <tr key={presetKey(preset)}>
                  <td>{preset.name}</td>
                  <td className="num">{preset.programs}</td>
                  <td className="num">{preset.operations}</td>
                  <td className="num">
                    {preset.changed > 0 ? <span className="differs">{preset.changed}</span> : 0}
                    {preset.unchecked > 0 && (
                      <small className="muted" title="Their speed or feed is a formula; scan the program again to check them">
                        {' '}+{preset.unchecked} not checked
                      </small>
                    )}
                  </td>
                  {presetValues(preset, display).map((value, index) => (
                    <td key={index} className="num">{value}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h3>
        Programs <span className="note">— anything different from the usual setup is marked</span>
      </h3>
      <div className="scroll">
        <table className="plain">
          <thead>
            <tr>
              <th>Program</th>
              <th className="num">Last saved</th>
              <th>Tool no.</th>
              <th>Holder</th>
              <th className="num">Stickout</th>
              <th>Machine</th>
              <th title="Marked when an operation ran at a different speed or feed than the preset">Cutting data</th>
              <th className="num" title="Operations that used the tool">OPs</th>
              <th className="num">Cutting time</th>
            </tr>
          </thead>
          <tbody>
            {detail.program_list.map((program) => (
              <tr key={program.file_id}>
                <td>{program.name}</td>
                <td className="num">{formatDate(program.last_saved)}</td>
                <td>
                  {program.tool_numbers.length === 0
                    ? NONE
                    : program.tool_numbers.map((number, index) => (
                        <span key={number.value}>
                          {index > 0 && ', '}
                          <Value usual={number.usual}>T{number.value}</Value>
                        </span>
                      ))}
                </td>
                <td>
                  {program.setups.map((setup, index) => (
                    <div key={index}>
                      <Value usual={setup.holder_usual}>{setup.holder || 'no holder'}</Value>
                    </div>
                  ))}
                </td>
                <td className="num">
                  {program.setups.map((setup, index) => (
                    <div key={index}>
                      <Value usual={setup.stickout_usual}>
                        {formatStickout(setup.stickout_min_mm, setup.stickout_max_mm, detail.units, display)}
                      </Value>
                    </div>
                  ))}
                </td>
                <td>
                  {program.machines.length === 0
                    ? NONE
                    : program.machines.map((machine) => (
                        <div key={machine.value}>
                          <Value usual={machine.usual}>{machine.value}</Value>
                        </div>
                      ))}
                </td>
                <td>
                  {program.presets.length === 0
                    ? NONE
                    : program.presets.map((preset) => (
                        <div key={preset.name}>
                          <Value usual={!preset.changed}>{preset.name}</Value>
                        </div>
                      ))}
                </td>
                <td className="num">{program.operations}</td>
                <td className="num">{formatDuration(program.time_s)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
