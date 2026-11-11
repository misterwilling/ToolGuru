import { useEffect, useState } from 'react'
import { sendToFusion, onFusionPush } from './api/fusionBridge'
import type { AppState } from './types'

export function App() {
  const [state, setState] = useState<AppState | null>(null)

  useEffect(() => {
    let cancelled = false
    sendToFusion('get_state').then((result) => {
      if (!cancelled) setState(result as AppState)
    })

    onFusionPush((action, data) => {
      if (action === 'state_update') {
        setState(data as AppState)
      }
    })

    return () => { cancelled = true }
  }, [])

  if (!state) return <div style={{ padding: 16 }}>Loading…</div>

  return (
    <div style={{ padding: 16, fontFamily: 'sans-serif' }}>
      <h1 style={{ fontSize: 18, marginTop: 0 }}>ToolGuru</h1>
      <p style={{ fontSize: 12, color: '#666' }}>Collects tools from CAM programs, tallies usage and finds duplicates to build a standard tool library.</p>
      <button onClick={() => sendToFusion('pick', { type: 'face', slot: 'primary' })}>
        Pick a face
      </button>
      <pre style={{ marginTop: 16, fontSize: 11, background: '#f4f4f4', padding: 8 }}>
        {JSON.stringify(state, null, 2)}
      </pre>
    </div>
  )
}
