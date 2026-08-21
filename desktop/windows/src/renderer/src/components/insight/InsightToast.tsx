// src/renderer/src/components/insight/InsightToast.tsx
// Rendered inside the shared acrylic toast window (#/insight-toast). Shows
// whichever payload arrived last: a proactive insight ('insight:payload') or a
// meeting-detection notice ('meeting:toast' — Phase 5). Main owns visibility +
// auto-dismiss; hover pause reuses the same IPC for both kinds.
import { useEffect, useState } from 'react'
import { useTranslation } from '../../i18n'
import type { InsightPayload, MeetingToastPayload, WhatsNewPayload } from '../../../../shared/types'
import './insight-toast.css'

type ToastContent =
  | { type: 'insight'; p: InsightPayload }
  | { type: 'meeting'; p: MeetingToastPayload }
  | { type: 'whatsnew'; p: WhatsNewPayload }

// Post-update changelog card (Phase 8). Shares the acrylic card shell; a compact
// list of the version's changes with the full notes one click away.
function WhatsNewCard({ p }: { p: WhatsNewPayload }): React.JSX.Element {
  const { t } = useTranslation()
  return (
    <div
      className="insight-card"
      onMouseEnter={() => window.omi.insightHoverStart()}
      onMouseLeave={() => window.omi.insightHoverEnd()}
    >
      <div className="insight-head">
        <span className="insight-cat">{t('insightToast.whatsNew')}</span>
        <button
          className="insight-x"
          onClick={() => window.omi.insightDismiss()}
          aria-label={t('insightToast.dismiss')}
        >
          ✕
        </button>
      </div>
      <div className="insight-headline">{t('insightToast.newInOmi', { version: p.version })}</div>
      <ul className="whatsnew-list">
        {p.changes.slice(0, 3).map((c, i) => (
          <li key={i}>{c}</li>
        ))}
      </ul>
      <div className="whatsnew-actions">
        <button
          className="meeting-btn meeting-btn-primary"
          onClick={() => window.omi.whatsNewOpenNotes()}
        >
          {t('insightToast.viewReleaseNotes')}
        </button>
      </div>
    </div>
  )
}

function MeetingCard({ p }: { p: MeetingToastPayload }): React.JSX.Element {
  const { t } = useTranslation()
  const capturing = p.kind === 'capturing'
  const starting = p.kind === 'starting'
  const failed = p.kind === 'error'
  const errorKind = p.errorKind ?? 'startup'
  return (
    <div
      className="insight-card"
      onMouseEnter={() => window.omi.insightHoverStart()}
      onMouseLeave={() => window.omi.insightHoverEnd()}
    >
      <div className="insight-head">
        <span className="insight-cat">{t('insightToast.meetingDetected')}</span>
        <button
          className="insight-x"
          onClick={() => window.omi.meetingAction(p.meetingId, 'dismiss')}
          aria-label={t('insightToast.dismiss')}
        >
          ✕
        </button>
      </div>
      <div className="insight-headline">
        {capturing
          ? t('insightToast.capturingHeadline', { app: p.appName })
          : starting
            ? t('insightToast.startingHeadline', { app: p.appName })
            : failed
              ? errorKind === 'runtime'
                ? t('insightToast.captureStopped', { app: p.appName })
                : errorKind === 'save'
                  ? t('insightToast.captureCouldNotSave', { app: p.appName })
                  : t('insightToast.captureDidNotStart', { app: p.appName })
              : t('insightToast.looksLikeMeeting', { app: p.appName })}
      </div>
      <div className="insight-advice">
        {capturing
          ? t('insightToast.adviceCapturing')
          : starting
            ? t('insightToast.adviceStarting')
            : failed
              ? errorKind === 'save'
                ? t('insightToast.adviceSaveFailed')
                : t('insightToast.adviceGenericFailed')
              : t('insightToast.adviceAsk')}
      </div>
      {p.firstRun ? <div className="insight-foot">{t('insightToast.firstRun')}</div> : null}
      <div className="meeting-actions">
        {capturing || starting ? (
          <button
            className="meeting-btn"
            onClick={() => window.omi.meetingAction(p.meetingId, 'stop')}
          >
            {starting ? t('insightToast.cancel') : t('insightToast.stop')}
          </button>
        ) : failed && errorKind === 'save' ? (
          <button
            className="meeting-btn"
            onClick={() => window.omi.meetingAction(p.meetingId, 'dismiss')}
          >
            {t('insightToast.dismiss')}
          </button>
        ) : (
          <>
            <button
              className="meeting-btn meeting-btn-primary"
              onClick={() => window.omi.meetingAction(p.meetingId, 'start')}
            >
              {failed ? t('insightToast.retry') : t('insightToast.startCapturing')}
            </button>
            <button
              className="meeting-btn"
              onClick={() => window.omi.meetingAction(p.meetingId, 'dismiss')}
            >
              {t('insightToast.notNow')}
            </button>
          </>
        )}
      </div>
    </div>
  )
}

export function InsightToast(): React.JSX.Element {
  const { t } = useTranslation()
  const [content, setContent] = useState<ToastContent | null>(null)

  useEffect(() => {
    document.body.classList.add('insight-toast-body')
    const offInsight = window.omi.onInsightShow((p) => setContent({ type: 'insight', p }))
    const offMeeting = window.omi.onMeetingToast((p) => setContent({ type: 'meeting', p }))
    const offWhatsNew = window.omi.onWhatsNewToast((p) => setContent({ type: 'whatsnew', p }))
    // Pull any pending payload: a push sent while this window was loading (meeting
    // detected — or the what's-new toast firing — right at startup) lands before
    // this effect subscribes and would otherwise be lost.
    void window.omi.meetingGetToast?.().then((p) => {
      if (p) setContent((cur) => cur ?? { type: 'meeting', p })
    })
    void window.omi.whatsNewGetPending?.().then((p) => {
      if (p) setContent((cur) => cur ?? { type: 'whatsnew', p })
    })
    return () => {
      document.body.classList.remove('insight-toast-body')
      offInsight()
      offMeeting()
      offWhatsNew()
    }
  }, [])

  if (!content) return <div className="insight-toast-body" />
  if (content.type === 'meeting') return <MeetingCard p={content.p} />
  if (content.type === 'whatsnew') return <WhatsNewCard p={content.p} />

  const insight = content.p
  return (
    <div
      className="insight-card"
      onMouseEnter={() => window.omi.insightHoverStart()}
      onMouseLeave={() => window.omi.insightHoverEnd()}
    >
      <div className="insight-head">
        <span className="insight-cat">{insight.category}</span>
        <button
          className="insight-x"
          onClick={() => window.omi.insightDismiss()}
          aria-label={t('insightToast.dismiss')}
        >
          ✕
        </button>
      </div>
      <div className="insight-headline">{insight.headline}</div>
      <div className="insight-advice">{insight.advice}</div>
      <div className="insight-foot">{insight.sourceApp}</div>
    </div>
  )
}
