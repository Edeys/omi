import { Monitor } from 'lucide-react'
import { PermissionStep } from './PermissionStep'
import { useTranslation } from '../../i18n'

type ScreenPermissionStepProps = {
  stepIndex: number
  totalSteps: number
  aside?: React.ReactNode
  onContinue: () => void
  onBack?: () => void
  onSkip?: () => void
}

export function ScreenPermissionStep({
  stepIndex,
  totalSteps,
  aside,
  onContinue,
  onBack,
  onSkip
}: ScreenPermissionStepProps): React.JSX.Element {
  const { t } = useTranslation()
  // Windows has NO OS consent prompt for desktop capture (unlike macOS Screen
  // Recording), so this is an honest opt-in, not a permission request: it turns
  // on Omi's local screen timeline (the Settings "Capture my screen" toggle).
  // No fake OS round-trip. If the write fails we say so and let the user retry or
  // skip; we never claim it's on when it isn't.
  const enableCapture = async (): Promise<void> => {
    try {
      const current = await window.omi.rewindGetSettings()
      if (!current.captureEnabled) {
        await window.omi.rewindSetSettings({ ...current, captureEnabled: true })
      }
    } catch {
      throw new Error(t('onboarding.screenPermission.error'))
    }
  }

  // Rewind capture defaults to ON (rewindSettings.ts DEFAULTS), so by the time this step
  // renders the screen is very likely ALREADY being captured. The step used to hard-code
  // an "Off" card with a "Turn on" button that did nothing, and Skip walked past it —
  // leaving capture running while the user believed they had declined. Read the real
  // setting instead, and make Skip mean what it says.
  const isCaptureOn = async (): Promise<boolean> =>
    (await window.omi.rewindGetSettings()).captureEnabled

  // Skip on this step is an explicit "no": turn capture off. Best-effort — a failed
  // write must not trap the user on the step, but it must not silently pass as consent
  // either, so the failure is surfaced and the step still advances.
  const declineCapture = (advance: () => void): void => {
    void (async () => {
      try {
        const current = await window.omi.rewindGetSettings()
        if (current.captureEnabled) {
          await window.omi.rewindSetSettings({ ...current, captureEnabled: false })
        }
      } catch (e) {
        console.warn('[onboarding] failed to disable screen capture on skip:', e)
      }
      advance()
    })()
  }

  return (
    <PermissionStep
      stepIndex={stepIndex}
      totalSteps={totalSteps}
      aside={aside}
      eyebrow={t('onboarding.screenPermission.eyebrow')}
      title={t('onboarding.screenPermission.title')}
      subtitle={t('onboarding.screenPermission.subtitle')}
      icon={<Monitor className="h-5 w-5 text-white/60" />}
      cardLabel={t('onboarding.screenPermission.cardLabel')}
      statusText={{
        idle: t('onboarding.screenPermission.status.idle'),
        waiting: t('onboarding.screenPermission.status.waiting'),
        granted: t('onboarding.screenPermission.status.granted'),
        denied: t('onboarding.screenPermission.status.denied')
      }}
      buttonLabel={{
        idle: t('onboarding.screenPermission.button.idle'),
        waiting: t('onboarding.screenPermission.button.waiting'),
        granted: t('onboarding.screenPermission.button.granted'),
        denied: t('onboarding.screenPermission.button.denied')
      }}
      onActivate={enableCapture}
      checkGranted={isCaptureOn}
      onContinue={onContinue}
      onBack={onBack}
      onSkip={onSkip ? () => declineCapture(onSkip) : undefined}
    />
  )
}
