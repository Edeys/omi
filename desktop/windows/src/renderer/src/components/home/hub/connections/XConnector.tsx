import { useEffect, useState } from 'react'
import { toast } from '../../../../lib/toast'
import { useTranslation } from '../../../../i18n'
import { useMemories } from '../../../../hooks/useMemories'
import { getXSession } from '../../../../lib/xSession'
import { ConnectorRow, PillButton } from './ConnectorRow'
import { ConnectorBrandMark } from './ConnectorBrandMark'
import { deriveView, friendlyError } from './xConnectorView'
import type { XStatus, XRunState } from '../../../../../../shared/types'

// X (Twitter) connector row. The connect run lives in main (so it outlives this
// panel); here we relay the session, kick it off, and reflect the streamed run
// state (connecting → syncing with live counts → succeeded). See main/integrations/
// xConnector.ts. Row-state derivation lives in xConnectorView.ts.

const IDLE_RUN: XRunState = { phase: 'idle', postCount: 0, memoryCount: 0 }

export function XConnector(): React.JSX.Element {
  const { t } = useTranslation()
  const { refresh } = useMemories()
  const [status, setStatus] = useState<XStatus | null>(null)
  const [run, setRun] = useState<XRunState>(IDLE_RUN)

  const refreshStatus = async (): Promise<void> => {
    const session = await getXSession()
    if (session) setStatus(await xStatusSafe(session))
  }

  useEffect(() => {
    let live = true
    void (async () => {
      const session = await getXSession()
      if (!session || !live) return
      xStatusSafe(session).then((s) => live && s && setStatus(s))
      window.omi
        .xRunState()
        .then((r) => live && setRun(r))
        .catch(() => {})
    })()
    const off = window.omi.onXProgress((r) => {
      setRun(r)
      if (r.phase === 'succeeded') {
        void refresh()
        void refreshStatus()
      }
    })
    return () => {
      live = false
      off()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const connect = async (): Promise<void> => {
    const session = await getXSession()
    if (!session) {
      toast(t('home.connections.xSignIn'), { tone: 'warn' })
      return
    }
    setRun(await window.omi.xConnect(session)) // seeds 'connecting'; progress streams in
  }

  const sync = async (): Promise<void> => {
    const session = await getXSession()
    if (!session) return
    try {
      const r = await window.omi.xSync(session)
      if (r.success)
        toast(t('home.connections.xSynced', { count: r.newPosts }), {
          tone: 'success'
        })
      else toast(t('home.connections.xSyncFailed'), { tone: 'error', body: friendlyError(r.error) })
      await refreshStatus()
      if (r.memoriesCreated > 0) await refresh()
    } catch (e) {
      toast(t('home.connections.xSyncFailed'), { tone: 'error', body: (e as Error).message })
    }
  }

  const disconnect = async (): Promise<void> => {
    const session = await getXSession()
    if (!session) return
    try {
      await window.omi.xDisconnect(session)
      setStatus({ connected: false, postCount: 0, memoryCount: 0, syncing: false })
      setRun(IDLE_RUN)
      toast(t('home.connections.xDisconnected'), { tone: 'success' })
    } catch (e) {
      toast(t('home.connections.xDisconnectFailed'), { tone: 'error', body: (e as Error).message })
    }
  }

  const view = deriveView(status, run)

  return (
    <ConnectorRow
      iconNode={<ConnectorBrandMark brand="x" />}
      title="X (Twitter)"
      description={view.description}
      action={
        view.state === 'connected' ? (
          <>
            <PillButton tone="neutral" onClick={sync} disabled={status?.syncing}>
              {status?.syncing ? 'Syncing…' : 'Sync now'}
            </PillButton>
            <PillButton tone="ghost" onClick={disconnect}>
              Disconnect
            </PillButton>
          </>
        ) : view.state === 'busy' ? (
          <PillButton tone="primary" disabled>
            {run.phase === 'syncing' ? 'Importing…' : 'Waiting…'}
          </PillButton>
        ) : (
          <PillButton tone="primary" onClick={connect}>
            Connect
          </PillButton>
        )
      }
    />
  )
}

// xStatus can legitimately fail (not configured / not connected yet); treat any
// failure as "not connected" rather than surfacing an error on mount.
async function xStatusSafe(session: { apiBase: string; token: string }): Promise<XStatus> {
  try {
    return await window.omi.xStatus(session)
  } catch {
    return { connected: false, postCount: 0, memoryCount: 0, syncing: false }
  }
}
