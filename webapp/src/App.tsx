import { useEffect, useState } from 'react'
// The add-in's icon: one drawing, shared with the toolbar button's PNG files.
import mark from '../../docs/icon/toolguru.svg'
import { onFusionPush, sendToFusion } from './api/fusionBridge'
import { CutterDetail } from './components/CutterDetail'
import { DatabasesPanel } from './components/DatabasesPanel'
import { ScanPanel } from './components/ScanPanel'
import { SimilarScreen } from './components/SimilarScreen'
import { Stats } from './components/Stats'
import { TallyTable } from './components/TallyTable'
import type { AppState, CountBy, LengthUnit } from './types'
import {
  countsSummary,
  formatTolerance,
  isAppState,
  toleranceToMm,
  uncreditedNote,
  writeLibraryLabel,
} from './utils'

export function App() {
  const [state, setState] = useState<AppState | null>(null)
  const [busy, setBusy] = useState(false)
  const [confirmReset, setConfirmReset] = useState(false)
  const [resetWord, setResetWord] = useState('')
  const [toleranceText, setToleranceText] = useState('')
  const [toleranceUnit, setToleranceUnit] = useState<LengthUnit>('in')
  const [bridgeError, setBridgeError] = useState('')

  async function run(action: string, data?: unknown): Promise<void> {
    setBusy(true)
    setConfirmReset(false)
    setResetWord('')
    const result = await sendToFusion(action, data)
    if (isAppState(result)) {
      setState(result)
      setBridgeError('')
    } else {
      setBridgeError('ToolGuru did not get an answer from Fusion. See View → Text Commands.')
    }
    setBusy(false)
  }

  // Follow Fusion's light or dark setting. Until Fusion has answered, the
  // style sheet falls back to the device's own setting.
  const theme = state?.theme
  useEffect(() => {
    if (theme) document.documentElement.dataset.theme = theme
  }, [theme])

  useEffect(() => {
    // Python pushes the state after each program of a folder scan.
    onFusionPush((action, data) => {
      if (action === 'state' && isAppState(data)) setState(data)
    })
    void run('get_state')
  }, [])

  if (!state) {
    return <div className="app">{bridgeError || 'Loading…'}</div>
  }

  const scanning = state.scan?.running === true
  // While a scan runs, only Stop works. A paused scan must be resumed or
  // dismissed before another folder is picked.
  const locked = busy || scanning
  const toleranceMm = toleranceToMm(toleranceText, toleranceUnit)
  // What the list counts: assemblies when counting by assembly, cutters otherwise.
  const assemblies = state.countBy === 'assembly' ? state.tally.length : undefined
  const summary = countsSummary(state.counts, assemblies)
  const unitButton = (value: LengthUnit) => (
    <button
      className={state.displayUnit === value ? 'selected' : undefined}
      disabled={busy || state.displayUnit === value}
      onClick={() => run('set_display_unit', { unit: value })}
    >
      {value}
    </button>
  )
  const countByButton = (value: CountBy, label: string) => (
    <button
      className={state.countBy === value ? 'selected' : undefined}
      disabled={busy || state.countBy === value}
      onClick={() => run('set_count_by', { countBy: value })}
    >
      {label}
    </button>
  )

  return (
    <div className="app">
      <header>
        <img className="mark" src={mark} alt="" />
        <h1>
          Tool<span>Guru</span>
        </h1>
      </header>

      <Stats counts={state.counts} assemblies={assemblies} />
      {state.uncreditedTimeS > 0 && (
        <p
          className="muted"
          title="A Mastercam transform repeats other operations. Its time is given to tools only when it is an exact multiple of the operations before it."
        >
          {uncreditedNote(state.uncreditedTimeS)}
        </p>
      )}

      <div className="actions">
        <button className="primary" disabled={locked} onClick={() => run('scan_active')}>
          {busy ? 'Working…' : 'Scan active document'}
        </button>
        <button
          disabled={locked || (state.scan?.pending ?? 0) > 0}
          onClick={() => run('browse_folder', { folderId: '' })}
        >
          Scan a folder…
        </button>
        <button
          title="Adds the programs in a scan file, such as the harvest.jsonl written by the Mastercam harvester"
          disabled={locked}
          onClick={() => run('import_scan_file')}
        >
          Import scan file…
        </button>
        <button
          className={state.similar ? 'selected' : undefined}
          disabled={busy || state.tally.length === 0}
          onClick={() => run(state.similar ? 'close_similar' : 'open_similar')}
        >
          Similar…
        </button>
        <button
          title="Writes the ticked cutters to the “ToolGuru Holding” library in Fusion's Local tool libraries"
          disabled={locked || state.libraryCount === 0}
          onClick={() => run('write_library')}
        >
          {writeLibraryLabel(state.libraryCount)}
        </button>
        <button
          className={state.databases ? 'selected' : undefined}
          disabled={busy}
          onClick={() => run(state.databases ? 'close_databases' : 'open_databases')}
        >
          Databases…
        </button>
        <button disabled={locked} onClick={() => setConfirmReset(true)}>Reset data</button>
      </div>

      {state.databases && (
        // A new panel each time the list changes, so a finished save or load
        // clears what was typed.
        <DatabasesPanel
          key={state.databases.map((database) => `${database.name}:${database.saved_at}`).join('|')}
          databases={state.databases}
          counts={state.counts}
          disabled={locked}
          run={run}
        />
      )}

      <ScanPanel state={state} busy={busy} run={run} />

      <div className="actions">
        <span>Show lengths in:</span>
        <span className="segmented">
          {unitButton('in')}
          {unitButton('mm')}
        </span>
        <span className="muted">A tool entered in the other unit shows that unit too.</span>
      </div>

      <div className="actions">
        <span>Count by:</span>
        <span className="segmented">
          {countByButton('cutter', 'Cutter')}
          {countByButton('assembly', 'Assembly')}
        </span>
        {state.countBy === 'cutter' ? (
          <span className="muted">The same cutter is one tool, whatever holder it was in.</span>
        ) : (
          <>
            <span className="muted">
              A different holder or stickout is a different tool. Stickouts within{' '}
              {formatTolerance(state.stickoutToleranceMm, state.displayUnit)} match.
            </span>
            <input
              className="short"
              placeholder="New tolerance"
              value={toleranceText}
              onChange={(event) => setToleranceText(event.target.value)}
            />
            <select
              value={toleranceUnit}
              onChange={(event) => setToleranceUnit(event.target.value as LengthUnit)}
            >
              <option value="in">in</option>
              <option value="mm">mm</option>
            </select>
            <button
              disabled={busy || toleranceMm === null}
              onClick={() => {
                setToleranceText('')
                void run('set_stickout_tolerance', { toleranceMm })
              }}
            >
              Set tolerance
            </button>
          </>
        )}
      </div>

      {confirmReset && (
        <div className="confirm">
          Remove {summary}? A backup copy is saved first. Type RESET to continue:
          <input value={resetWord} onChange={(event) => setResetWord(event.target.value)} />
          <button disabled={resetWord !== 'RESET'} onClick={() => run('reset_data', { confirm: resetWord })}>
            Reset data
          </button>
          <button onClick={() => setConfirmReset(false)}>Cancel</button>
        </div>
      )}

      {bridgeError && <div className="message error">{bridgeError}</div>}
      {state.error && <div className="message error">{state.error}</div>}
      {state.notice && <div className="message notice">{state.notice}</div>}
      {state.lastScan && (
        <div className="message notice">
          Scanned “{state.lastScan.name}”: {state.lastScan.operations} operations using{' '}
          {state.lastScan.cutters} cutters
          {state.lastScan.operationsWithoutTime > 0 &&
            ` (${state.lastScan.operationsWithoutTime} without a saved cutting time)`}
          .
        </div>
      )}

      {state.similar && (
        <SimilarScreen similar={state.similar} display={state.displayUnit} disabled={locked} run={run} />
      )}
      {state.detail && !state.similar && (
        <CutterDetail
          detail={state.detail}
          display={state.displayUnit}
          picture={state.toolPictures?.[state.detail.tool_type]}
          busy={busy}
          onClose={() => run('close_cutter')}
          onSplit={() => run('split_cutters', { cutterKey: state.detail?.cutter_key })}
          onPick={(picked, assemblyKey) =>
            run('pick_for_library', { cutterKey: state.detail?.cutter_key, picked, assemblyKey })
          }
        />
      )}
      {state.tally.length === 0 ? (
        <p className="muted">
          No tools yet. Open a program and click “Scan active document”, scan a folder, or import a scan
          file.
        </p>
      ) : (
        // Hidden, not removed, while a detail is open: the sort and filter are kept.
        <div hidden={state.detail !== null || state.similar !== null}>
          <TallyTable
            rows={state.tally}
            countBy={state.countBy}
            display={state.displayUnit}
            descriptionWidth={state.descriptionWidthPx}
            onResized={(widthPx) => run('set_description_width', { widthPx })}
            onOpen={(cutterKey) => run('show_cutter', { cutterKey })}
            locked={locked}
            onPick={(cutterKey, picked, assemblyKey) => run('pick_for_library', { cutterKey, picked, assemblyKey })}
            onPickMany={(lines, picked) => run('pick_many_for_library', { lines, picked })}
          />
        </div>
      )}
    </div>
  )
}
