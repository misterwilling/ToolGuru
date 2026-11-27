import { useState } from 'react'
import type { Counts, SavedDatabase } from '../types'
import { countsSummary, findSaved, formatDate, savedSummary } from '../utils'

interface Props {
  databases: SavedDatabase[]
  counts: Counts // what is on screen now
  disabled: boolean
  run: (action: string, data?: unknown) => Promise<void>
}

/** Saved databases: save what is on screen under a name, or load one. */
export function DatabasesPanel({ databases, counts, disabled, run }: Props) {
  const [name, setName] = useState('')
  const [loading, setLoading] = useState<string | null>(null) // the one being loaded
  const taken = findSaved(databases, name)
  const nothingToSave = counts.documents === 0

  return (
    <div className="panel databases">
      <div className="panel-head">
        <b>Databases</b>
        <button className="link" disabled={disabled} onClick={() => run('close_databases')}>
          Close
        </button>
      </div>

      <div className="actions">
        <span>Save what is on screen as:</span>
        <input
          placeholder="Name"
          maxLength={60}
          value={name}
          disabled={nothingToSave}
          onChange={(event) => setName(event.target.value)}
        />
        <button
          className={taken ? undefined : 'primary'}
          disabled={disabled || nothingToSave || name.trim() === ''}
          onClick={() => run('save_database', { name, replace: taken !== undefined })}
        >
          {taken ? `Replace “${taken.name}”` : 'Save'}
        </button>
        {nothingToSave ? (
          <span className="muted">Nothing is scanned yet, so there is nothing to save.</span>
        ) : (
          taken && <span className="muted">That name is already saved. Saving replaces it.</span>
        )}
      </div>

      {databases.length === 0 ? (
        <p className="muted">Nothing saved yet.</p>
      ) : (
        <table className="saved">
          <thead>
            <tr>
              <th>Name</th>
              <th>Saved</th>
              <th>Holds</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {databases.map((database) => (
              <tr key={database.name}>
                <td>
                  <b>{database.name}</b>
                </td>
                <td>{formatDate(database.saved_at)}</td>
                <td>{savedSummary(database)}</td>
                <td className="saved-load">
                  <button
                    disabled={disabled || database.counts === null}
                    onClick={() => setLoading(database.name)}
                  >
                    Load…
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {loading !== null && (
        <div className="confirm load-choice">
          {nothingToSave ? (
            <div className="choice">
              <button disabled={disabled} onClick={() => run('load_database', { name: loading, mode: 'replace' })}>
                Load “{loading}”
              </button>
              <button onClick={() => setLoading(null)}>Cancel</button>
            </div>
          ) : (
            <>
              <b>How should “{loading}” be loaded?</b>
              <div className="choice">
                <button disabled={disabled} onClick={() => run('load_database', { name: loading, mode: 'replace' })}>
                  Replace
                </button>
                <span>
                  Show only “{loading}”. The {countsSummary(counts)} showing now are taken off the screen, and a
                  backup copy of them is saved first.
                </span>
              </div>
              <div className="choice">
                <button disabled={disabled} onClick={() => run('load_database', { name: loading, mode: 'add' })}>
                  Merge
                </button>
                <span>
                  Combine “{loading}” with what is showing now. Nothing is removed, and a program that is in both is
                  counted once.
                </span>
              </div>
              <div className="choice">
                <button onClick={() => setLoading(null)}>Cancel</button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
