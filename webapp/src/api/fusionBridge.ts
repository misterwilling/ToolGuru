// Communication bridge between the React palette and the Fusion Python backend.
// See ARCHITECTURE.md "Python-React Communication" for the full contract.

declare const adsk: {
  fusionSendData: (action: string, data: string) => Promise<string>
} | undefined

function waitForBridge(): Promise<boolean> {
  return new Promise((resolve) => {
    if (typeof adsk !== 'undefined') { resolve(true); return }
    let attempts = 0
    const interval = setInterval(() => {
      attempts++
      if (typeof adsk !== 'undefined') {
        clearInterval(interval); resolve(true)
      } else if (attempts > 50) {
        // 5 seconds — palette loaded outside Fusion, or bridge failed to inject.
        clearInterval(interval); resolve(false)
      }
    }, 100)
  })
}

const bridgeReady = waitForBridge()

export async function sendToFusion(action: string, data?: unknown): Promise<unknown> {
  await bridgeReady
  if (typeof adsk === 'undefined') return null
  try {
    const response = await adsk.fusionSendData(action, JSON.stringify(data ?? {}))
    try { return JSON.parse(response) } catch { return response }
  } catch (err) {
    console.error(`[fusionBridge] Error in ${action}:`, err)
    return null
  }
}

export function onFusionPush(callback: (action: string, data: unknown) => void): void {
  // Fusion injects this global and calls .handle() on every push from Python.
  (window as unknown as { fusionJavaScriptHandler: { handle: (a: string, d: string) => void } })
    .fusionJavaScriptHandler = {
      handle: (action: string, data: string) => {
        try { callback(action, JSON.parse(data)) }
        catch { callback(action, data) }
      },
    }
}
