import { useEffect, useState } from 'react'
import { onFusionPush, sendToFusion } from './api/fusionBridge'
import { ScanPanel } from './components/ScanPanel'
import { TallyTable } from './components/TallyTable'
import type { AppState, CountBy, Dataset, LengthUnit } from './types'
import { countsSummary, datasetBadge, formatTolerance, isAppState, toleranceToMm } from './utils'

type Confirm = 'none' | 'clear_trial' | 'reset_main' | 'switch_main'

export function App() {
  const [state, setState] = useState<AppState | null>(null)
  const [busy, setBusy] = useState(false)
  const [confirm, setConfirm] = useState<Confirm>('none')
  const [resetWord, setResetWord] = useState('')
  const [toleranceText, setToleranceText] = useState('')
  const [toleranceUnit, setToleranceUnit] = useState<LengthUnit>('in')
  const [bridgeError, setBridgeError] = useState('')

  async function run(action: string, data?: unknown): Promise<void> {
    setBusy(true)
    setConfirm('none')
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

  const badge = datasetBadge(state.dataset)
  const scanning = state.scan?.running === true
  // While a scan runs, only Stop works. A paused scan must be resumed or
  // dismissed before another folder is picked.
  const locked = busy || scanning
  const other: Dataset = state.dataset === 'trial' ? 'main' : 'trial'
  const toleranceMm = toleranceToMm(toleranceText, toleranceUnit)
  const summary = countsSummary(state.counts, state.countBy === 'assembly' ? state.tally.length : undefined)
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
        <h1>ToolGuru</h1>
        <span className={`badge ${badge.tone}`}>{badge.label}</span>
        <span className="muted">{summary}</span>
        <button
          className="link"
          disabled={locked}
          onClick={() => (other === 'main' ? setConfirm('switch_main') : run('set_dataset', { dataset: 'trial' }))}
        >
          Switch to {other} data
        </button>
      </header>

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
        {state.dataset === 'trial' ? (
          <button disabled={locked} onClick={() => setConfirm('clear_trial')}>Clear trial data</button>
        ) : (
          <button disabled={locked} onClick={() => setConfirm('reset_main')}>Reset main data</button>
        )}
      </div>

      <ScanPanel state={state} busy={busy} run={run} />

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
              {formatTolerance(state.stickoutToleranceMm)} match.
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

      {confirm === 'switch_main' && (
        <div className="confirm">
          Switch to the MAIN data? Scans will be added to your real tally.
          <button onClick={() => run('set_dataset', { dataset: 'main' })}>Switch to main</button>
          <button onClick={() => setConfirm('none')}>Cancel</button>
        </div>
      )}
      {confirm === 'clear_trial' && (
        <div className="confirm">
          Remove {summary} from the trial data? Main data is not touched.
          <button onClick={() => run('clear_trial')}>Clear trial data</button>
          <button onClick={() => setConfirm('none')}>Cancel</button>
        </div>
      )}
      {confirm === 'reset_main' && (
        <div className="confirm">
          Remove {summary} from the MAIN data? A backup copy is saved first.
          Type RESET to continue:
          <input value={resetWord} onChange={(event) => setResetWord(event.target.value)} />
          <button disabled={resetWord !== 'RESET'} onClick={() => run('reset_main', { confirm: resetWord })}>
            Reset main data
          </button>
          <button onClick={() => setConfirm('none')}>Cancel</button>
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

      {state.tally.length === 0 ? (
        <p className="muted">
          No tools yet. Open a program and click “Scan active document”, or scan a folder.
        </p>
      ) : (
        <TallyTable rows={state.tally} countBy={state.countBy} />
      )}
    </div>
  )
}
