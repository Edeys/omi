import { useEffect, useState } from 'react'
import { Mic, AppWindow, Power, type LucideIcon } from 'lucide-react'
import { Toggle } from '../settings/Toggle'
import { useTranslation } from '../../i18n'

// The three items every background/privacy consent surface shows. Shared by the
// onboarding step (BackgroundPrivacyStep) and the one-time interstitial for
// existing users so the wording and layout stay in lockstep. Continuous
// listening and launch-at-login are user-controlled; running in the tray is
// informational (always on for a resident companion app), shown as a static
// "Always on" chip rather than a toggle.
type Props = {
  listening: boolean
  onListeningChange: (next: boolean) => void
  launchAtLogin: boolean
  onLaunchAtLoginChange: (next: boolean) => void
}

function Row(props: {
  icon: LucideIcon
  title: string
  detail: string
  control: React.ReactNode
}): React.JSX.Element {
  const { icon: Icon, title, detail, control } = props
  return (
    <div className="flex w-full items-center gap-4 rounded-xl bg-white/[0.06] px-5 py-3.5 text-left">
      <Icon className="h-6 w-6 shrink-0 text-white/80" strokeWidth={1.75} />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-white">{title}</p>
        <p className="mt-0.5 text-xs leading-relaxed text-white/60">{detail}</p>
      </div>
      <div className="shrink-0">{control}</div>
    </div>
  )
}

export function BackgroundConsentControls({
  listening,
  onListeningChange,
  launchAtLogin,
  onLaunchAtLoginChange
}: Props): React.JSX.Element {
  const { t } = useTranslation()
  // Launch-at-login is only writable in packaged builds (see the app:get-login-item
  // handler). In unpackaged dev the card stays visible but its toggle is disabled
  // so the UI never offers a switch that silently does nothing.
  const [launchSupported, setLaunchSupported] = useState(true)
  useEffect(() => {
    void window.omi?.getLoginItemSettings?.().then((s) => setLaunchSupported(!!s?.supported))
  }, [])

  return (
    <div className="flex w-full flex-col gap-3">
      <Row
        icon={Mic}
        title={t('onboarding.backgroundPrivacy.continuousTitle')}
        detail={t('onboarding.backgroundPrivacy.continuousDetail')}
        control={
          <Toggle
            on={listening}
            onChange={onListeningChange}
            label={t('onboarding.backgroundPrivacy.continuousTitle')}
          />
        }
      />
      <Row
        icon={AppWindow}
        title={t('onboarding.backgroundPrivacy.backgroundTitle')}
        detail={t('onboarding.backgroundPrivacy.backgroundDetail')}
        control={
          <span className="rounded-full bg-white/10 px-2.5 py-1 text-xs font-medium text-white/70">
            {t('onboarding.backgroundPrivacy.backgroundChip')}
          </span>
        }
      />
      <Row
        icon={Power}
        title={t('onboarding.backgroundPrivacy.launchTitle')}
        detail={
          launchSupported
            ? t('onboarding.backgroundPrivacy.launchDetail')
            : t('onboarding.backgroundPrivacy.launchDetailUninstalled')
        }
        control={
          <Toggle
            on={launchAtLogin}
            onChange={onLaunchAtLoginChange}
            disabled={!launchSupported}
            label={t('onboarding.backgroundPrivacy.launchTitle')}
          />
        }
      />
    </div>
  )
}
