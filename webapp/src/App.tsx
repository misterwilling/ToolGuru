import { useEffect, useState } from 'react'
import { sendToFusion } from './api/fusionBridge'
import { TallyTable } from './components/TallyTable'
import type { AppState, Dataset } from './types'
import { countsSummary, datasetBadge, isAppState } from './utils'

type Confirm = 'none' | 'clear_trial' | 'reset_main' | 'switch_main'

export function App() {
  const [state, setState] = useState<AppState | null>(null)
  const [busy, setBusy] = useState(false)
  const [confirm, setConfirm] = useState<Confirm>('none')
  const [resetWord, setResetWord] = useState('')
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
    void run('get_state')
  }, [])

  if (!state) {
    return <div className="app">{bridgeError || 'Loading…'}</div>
  }

  const badge = datasetBadge(state.dataset)
  const other: Dataset = state.dataset === 'trial' ? 'main' : 'trial'

  return (
    <div className="app">
      <header>
        <h1>ToolGuru</h1>
        <span className={`badge ${badge.tone}`}>{badge.label}</span>
        <span className="muted">{countsSummary(state.counts)}</span>
        <button
          className="link"
          disabled={busy}
          onClick={() => (other === 'main' ? setConfirm('switch_main') : run('set_dataset', { dataset: 'trial' }))}
        >
          Switch to {other} data
        </button>
      </header>

      <div className="actions">
        <button className="primary" disabled={busy} onClick={() => run('scan_active')}>
          {busy ? 'Working…' : 'Scan active document'}
        </button>
        {state.dataset === 'trial' ? (
          <button disabled={busy} onClick={() => setConfirm('clear_trial')}>Clear trial data</button>
        ) : (
          <button disabled={busy} onClick={() => setConfirm('reset_main')}>Reset main data</button>
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
          Remove {countsSummary(state.counts)} from the trial data? Main data is not touched.
          <button onClick={() => run('clear_trial')}>Clear trial data</button>
          <button onClick={() => setConfirm('none')}>Cancel</button>
        </div>
      )}
      {confirm === 'reset_main' && (
        <div className="confirm">
          Remove {countsSummary(state.counts)} from the MAIN data? A backup copy is saved first.
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
          No tools yet. Open a program and click “Scan active document”.
        </p>
      ) : (
        <TallyTable rows={state.tally} />
      )}
    </div>
  )
}
