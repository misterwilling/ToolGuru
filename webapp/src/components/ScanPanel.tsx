import { useState } from 'react'
import type { AppState } from '../types'
import { browserHere, scanHeadline, scanOutcome, scanPercent } from '../utils'

interface Props {
  state: AppState
  busy: boolean
  run: (action: string, data?: unknown) => Promise<void>
}

/** Folder scan: pick a folder, confirm the count, watch it run. */
export function ScanPanel({ state, busy, run }: Props) {
  const [includeSubfolders, setIncludeSubfolders] = useState(false)
  const { browser, confirmScan, scan } = state

  return (
    <>
      {browser && !scan?.running && (
        <div className="panel">
          <div className="crumbs">
            <button className="link" disabled={busy} onClick={() => run('browse_folder', { folderId: '' })}>
              Projects
            </button>
            {browser.path.map((entry) => (
              <span key={entry.id}>
                {' / '}
                <button className="link" disabled={busy} onClick={() => run('browse_folder', { folderId: entry.id })}>
                  {entry.name}
                </button>
              </span>
            ))}
          </div>
          <ul className="folders">
            {browser.folders.map((folder) => (
              <li key={folder.id}>
                <button className="link" disabled={busy} onClick={() => run('browse_folder', { folderId: folder.id })}>
                  {folder.name}
                </button>
              </li>
            ))}
          </ul>
          <div className="actions">
            <span className="muted">{browserHere(browser)}</span>
            {browser.folderId !== '' && (
              <>
                <label>
                  <input
                    type="checkbox"
                    checked={includeSubfolders}
                    onChange={(event) => setIncludeSubfolders(event.target.checked)}
                  />{' '}
                  Include subfolders
                </label>
                <button
                  disabled={busy}
                  onClick={() => run('count_folder', { folderId: browser.folderId, includeSubfolders })}
                >
                  Count designs in this folder
                </button>
              </>
            )}
            <button disabled={busy} onClick={() => run('close_folder_picker')}>Cancel</button>
          </div>
        </div>
      )}

      {confirmScan && (
        <div className="confirm">
          “{confirmScan.folder}” contains {confirmScan.count} Fusion{' '}
          {confirmScan.count === 1 ? 'design' : 'designs'}. Scan {confirmScan.count === 1 ? 'it' : 'them'}?
          Each one is opened, read and closed without saving.
          <button className="primary" disabled={busy} onClick={() => run('start_folder_scan')}>
            Start scan
          </button>
          <button disabled={busy} onClick={() => run('close_folder_picker')}>Cancel</button>
        </div>
      )}

      {scan && (
        <div className="panel">
          <div className="actions">
            <strong>{scanHeadline(scan)}</strong>
            <span className="muted">{scanOutcome(scan)}</span>
            {scan.running && <button onClick={() => run('stop_scan')}>Stop</button>}
            {!scan.running && scan.pending > 0 && (
              <button className="primary" disabled={busy} onClick={() => run('resume_scan')}>
                Resume
              </button>
            )}
            {!scan.running && (
              <button disabled={busy} onClick={() => run('dismiss_scan')}>Dismiss</button>
            )}
          </div>
          <div className="progress">
            <div style={{ width: `${scanPercent(scan)}%` }} />
          </div>
          {scan.problems.length > 0 && (
            <ul className="problems">
              {scan.problems.map((problem, index) => (
                <li key={index} className={problem.status}>
                  <strong>{problem.status === 'failed' ? 'Failed' : 'Skipped'}:</strong> {problem.name} —{' '}
                  {problem.message}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </>
  )
}
