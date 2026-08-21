import { useEffect, useState } from 'react'
import { StickyNote, Mail, Inbox } from 'lucide-react'
import { toast } from '../../../lib/toast'
import { readAndExtractStickyNotes, importStickyMemories } from '../../../lib/stickyNotesImport'
import { toastImportTally } from '../../../lib/importToast'
import { useMemories } from '../../../hooks/useMemories'
import { useGoogleConnection } from '../../../hooks/useGoogleConnection'
import { GMAIL_SESSION_ENABLED } from '../../../lib/gmailSessionFeatureFlag'
import { auth } from '../../../lib/firebase'
import { SettingRow } from '../SettingRow'
import { useTranslation } from '../../../i18n'
import type { GmailSessionStatus } from '../../../../../shared/types'

export function IntegrationsTab(): React.JSX.Element {
  const { memories, refresh } = useMemories()
  const { t } = useTranslation()

  // --- Sticky Notes ---
  const [stickyReading, setStickyReading] = useState(false)
  const [stickyImporting, setStickyImporting] = useState(false)
  const [stickyMemories, setStickyMemories] = useState<string[] | null>(null)
  const [stickyProfile, setStickyProfile] = useState('')

  const readSticky = async (): Promise<void> => {
    if (stickyReading || stickyImporting) return
    setStickyReading(true)
    setStickyMemories(null)
    setStickyProfile('')
    try {
      const outcome = await readAndExtractStickyNotes(memories.map((m) => m.content))
      if (outcome.status === 'unavailable')
        toast(t('settings.advanced.noStickyFound'), { tone: 'warn' })
      else if (outcome.status === 'error')
        toast(t('settings.advanced.stickyReadFailed'), { tone: 'error', body: outcome.error })
      else if (outcome.status === 'empty')
        toast(
          outcome.reason === 'no-notes'
            ? t('settings.advanced.stickyNoNotes')
            : t('settings.advanced.stickyNoNew'),
          { tone: 'warn' }
        )
      else {
        setStickyMemories(outcome.memories)
        setStickyProfile(outcome.profile)
      }
    } catch (e) {
      toast(t('settings.advanced.stickyCouldNotRead'), {
        tone: 'error',
        body: (e as Error).message
      })
    } finally {
      setStickyReading(false)
    }
  }

  const importSticky = async (): Promise<void> => {
    if (!stickyMemories || stickyMemories.length === 0 || stickyImporting) return
    setStickyImporting(true)
    const tally = await importStickyMemories(stickyMemories, stickyProfile)
    setStickyImporting(false)
    toastImportTally(tally)
    if (tally.ok > 0) await refresh()
    if (!tally.failed) {
      setStickyMemories(null)
      setStickyProfile('')
    }
  }

  // --- Google --- (client-side Gmail lane; shared with the Hub Email card, incl.
  // the sync-on-connect + 15-min background resync, via the singleton hook.)
  const {
    googleEnabled,
    status: googleStatus,
    connect: connectGoogle,
    disconnect: disconnectGoogle,
    syncNow: runSync,
    busy: googleBusy,
    syncing: googleSyncing
  } = useGoogleConnection()

  // --- Gmail (session): Option B. Sign into Google once inside an Omi-owned window;
  // we replay Gmail's web endpoints against that persisted session (no OAuth scopes). ---
  const [gmailStatus, setGmailStatus] = useState<GmailSessionStatus>({ connected: false })
  const [gmailBusy, setGmailBusy] = useState(false)
  const [gmailFetching, setGmailFetching] = useState(false)

  useEffect(() => {
    if (!GMAIL_SESSION_ENABLED) return
    window.omi
      .gmailSessionStatus()
      .then(setGmailStatus)
      .catch(() => {})
  }, [])

  const connectGmail = async (): Promise<void> => {
    if (gmailBusy) return
    setGmailBusy(true)
    try {
      // Pre-select the account: pass the signed-in Omi user's Google email so Google
      // lands on "Continue as <account>" instead of an empty identifier field.
      const next = await window.omi.gmailSessionConnect(auth.currentUser?.email ?? undefined)
      setGmailStatus(next)
      if (next.connected) toast(t('settings.advanced.gmailConnected'), { tone: 'success' })
      else if (next.message)
        toast(t('settings.advanced.gmailNotConnected'), { tone: 'warn', body: next.message })
    } catch (e) {
      toast(t('settings.advanced.gmailCouldNotConnect'), {
        tone: 'error',
        body: (e as Error).message
      })
    } finally {
      setGmailBusy(false)
    }
  }

  const fetchGmail = async (): Promise<void> => {
    if (gmailFetching) return
    setGmailFetching(true)
    try {
      const res = await window.omi.gmailSessionFetch('newer_than:7d', 25)
      if (res.ok) {
        toast(
          t('settings.advanced.gmailReadCount', {
            count: res.emails.length,
            plural: res.emails.length === 1 ? '' : 's'
          }),
          {
            tone: 'success'
          }
        )
      } else {
        toast(t('settings.advanced.gmailCouldNotRead'), { tone: 'warn', body: res.error })
        // Network-probe the session (not the cheap cookie check): a stale-but-present
        // session verifies as disconnected, flipping the row back to a Connect prompt.
        setGmailStatus(await window.omi.gmailSessionVerify())
      }
    } catch (e) {
      toast(t('settings.advanced.gmailCouldNotRead'), { tone: 'error', body: (e as Error).message })
    } finally {
      setGmailFetching(false)
    }
  }

  const disconnectGmail = async (): Promise<void> => {
    if (gmailBusy) return
    setGmailBusy(true)
    try {
      setGmailStatus(await window.omi.gmailSessionDisconnect())
      toast(t('settings.advanced.gmailDisconnected'), { tone: 'success' })
    } catch (e) {
      toast(t('settings.advanced.gmailCouldNotDisconnect'), {
        tone: 'error',
        body: (e as Error).message
      })
    } finally {
      setGmailBusy(false)
    }
  }

  return (
    <>
      <SettingRow
        icon={StickyNote}
        title={t('settings.advanced.integrationsStickyTitle')}
        subtitle={t('settings.advanced.integrationsStickySubtitle')}
        keywords="sticky notes import integration"
        control={
          <div className="flex items-center gap-2">
            <button
              onClick={readSticky}
              disabled={stickyReading || stickyImporting}
              className="btn-ghost disabled:opacity-40"
            >
              {stickyReading ? t('settings.advanced.reading') : t('settings.advanced.readNotes')}
            </button>
            {stickyMemories && stickyMemories.length > 0 && (
              <button
                onClick={importSticky}
                disabled={stickyImporting}
                className="btn-primary px-4 py-2 disabled:opacity-40"
              >
                {stickyImporting
                  ? t('settings.advanced.importing')
                  : t('settings.advanced.importButton', {
                      count: stickyMemories.length,
                      plural: stickyMemories.length === 1 ? 'y' : 'ies'
                    })}
              </button>
            )}
          </div>
        }
      >
        {stickyProfile && (
          <p className="glass-subtle mb-2 rounded-lg px-4 py-3 text-sm italic text-text-tertiary">
            {stickyProfile}
          </p>
        )}
        {stickyMemories && stickyMemories.length > 0 && (
          <ul className="glass-subtle max-h-40 overflow-y-auto rounded-lg px-4 py-3 text-sm text-text-tertiary">
            {stickyMemories.map((m, i) => (
              <li key={i} className="py-0.5">
                • {m}
              </li>
            ))}
          </ul>
        )}
      </SettingRow>

      {googleEnabled && (
        <SettingRow
          icon={Mail}
          dot={googleStatus.connected ? 'on' : 'off'}
          title={t('settings.advanced.googleTitle')}
          subtitle={
            googleStatus.connected
              ? t('settings.advanced.googleConnected', {
                  email: googleStatus.email
                    ? t('settings.advanced.googleConnectedAs', { email: googleStatus.email })
                    : '',
                  sync: googleStatus.lastSyncAt
                    ? t('settings.advanced.googleLastSync', {
                        date: new Date(googleStatus.lastSyncAt).toLocaleString()
                      })
                    : ''
                })
              : t('settings.advanced.googleSubtitleDisconnected')
          }
          keywords="google gmail calendar sync integration"
          control={
            googleStatus.connected ? (
              <div className="flex items-center gap-2">
                <button
                  onClick={runSync}
                  disabled={googleSyncing}
                  className="btn-primary px-4 py-2 disabled:opacity-40"
                >
                  {googleSyncing ? t('settings.advanced.syncing') : t('settings.advanced.syncNow')}
                </button>
                <button
                  onClick={disconnectGoogle}
                  disabled={googleBusy}
                  className="btn-ghost disabled:opacity-40"
                >
                  {t('settings.advanced.disconnect')}
                </button>
              </div>
            ) : (
              <button
                onClick={connectGoogle}
                disabled={googleBusy}
                className="btn-ghost disabled:opacity-40"
              >
                {googleBusy ? t('settings.advanced.connecting') : t('settings.advanced.connect')}
              </button>
            )
          }
        />
      )}

      {GMAIL_SESSION_ENABLED && (
        <SettingRow
          icon={Inbox}
          dot={gmailStatus.connected ? 'on' : 'off'}
          title={t('settings.advanced.gmailSessionTitle')}
          subtitle={
            gmailStatus.connected
              ? t('settings.advanced.gmailConnectedSubtitle')
              : gmailStatus.message || t('settings.advanced.gmailDisconnectedSubtitle')
          }
          keywords="gmail session email inbox connect integration"
          control={
            gmailStatus.connected ? (
              <div className="flex items-center gap-2">
                <button
                  onClick={fetchGmail}
                  disabled={gmailFetching}
                  className="btn-primary px-4 py-2 disabled:opacity-40"
                >
                  {gmailFetching
                    ? t('settings.advanced.reading')
                    : t('settings.advanced.fetchRecent')}
                </button>
                <button
                  onClick={disconnectGmail}
                  disabled={gmailBusy}
                  className="btn-ghost disabled:opacity-40"
                >
                  {t('settings.advanced.disconnect')}
                </button>
              </div>
            ) : (
              <button
                onClick={connectGmail}
                disabled={gmailBusy}
                className="btn-ghost disabled:opacity-40"
              >
                {gmailBusy ? t('settings.advanced.connecting') : t('settings.advanced.connect')}
              </button>
            )
          }
        />
      )}
    </>
  )
}
