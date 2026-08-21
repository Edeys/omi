import { Mic } from 'lucide-react'
import { PermissionStep } from './PermissionStep'
import { setPreferences } from '../../lib/preferences'
import { useTranslation } from '../../i18n'

type MicPermissionStepProps = {
  stepIndex: number
  totalSteps: number
  aside?: React.ReactNode
  onContinue: () => void
  onBack?: () => void
  onSkip?: () => void
}

/**
 * Read the real Windows microphone permission without prompting, so a mic the user
 * already allowed shows as allowed (and one they allow in Windows Settings mid-step is
 * picked up on the next poll / on refocus).
 *
 * This asks MAIN, which reads the Capability Access Manager registry. It deliberately
 * does NOT use `navigator.permissions.query({name:'microphone'})`: Electron registers no
 * permission-check handler, so Chromium answers 'granted' unconditionally — including on
 * a fresh profile with the mic blocked by Windows. Trusting it made this step
 * false-grant and skip itself on every run, without ever asking the OS.
 *
 * Unknown/unreadable reads as not-granted: never assume a grant we can't see.
 */
async function isMicGranted(): Promise<boolean> {
  try {
    return (await window.omi?.getMicPermissionState?.()) === 'granted'
  } catch {
    return false
  }
}

export function MicPermissionStep({
  stepIndex,
  totalSteps,
  aside,
  onContinue,
  onBack,
  onSkip
}: MicPermissionStepProps): React.JSX.Element {
  const { t } = useTranslation()
  // Trigger the real Windows microphone grant. getUserMedia surfaces the OS
  // prompt; we immediately release the device since we only needed the grant.
  // A denial REJECTS — PermissionStep turns that into an explicit denied state
  // (never "Granted", never an auto-advance).
  const requestAccess = async (): Promise<void> => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      stream.getTracks().forEach((t) => t.stop())
    } catch (e) {
      const err = e as Error
      throw new Error(
        err.name === 'NotAllowedError'
          ? t('onboarding.micPermission.errorBlocked')
          : t('onboarding.micPermission.errorFailed', { message: err.message })
      )
    }
  }

  // Granting the mic opts into always-on listening — continuous recording is on
  // from here (the background host starts streaming once onboarding completes).
  // One step, no separate continuous-recording screen; toggle it off anytime via
  // the sidebar mic switch or Settings.
  //
  // PermissionStep only calls this when the user AFFIRMATIVELY takes the permission —
  // their own grant click, or Continue on a mic we found already allowed. It is never
  // called off a bare detection or a Skip, so always-on mic streaming can no longer be
  // switched on by a grant that never happened.
  const handleGranted = (): void => {
    setPreferences({ continuousRecording: true })
  }

  return (
    <PermissionStep
      stepIndex={stepIndex}
      totalSteps={totalSteps}
      aside={aside}
      eyebrow={t('onboarding.micPermission.eyebrow')}
      title={t('onboarding.micPermission.title')}
      subtitle={t('onboarding.micPermission.subtitle')}
      icon={<Mic className="h-5 w-5 text-white/60" />}
      cardLabel={t('onboarding.micPermission.cardLabel')}
      statusText={{
        idle: t('onboarding.micPermission.status.idle'),
        waiting: t('onboarding.micPermission.status.waiting'),
        granted: t('onboarding.micPermission.status.granted'),
        denied: t('onboarding.micPermission.status.denied')
      }}
      buttonLabel={{
        idle: t('onboarding.micPermission.button.idle'),
        waiting: t('onboarding.micPermission.button.waiting'),
        granted: t('onboarding.micPermission.button.granted'),
        denied: t('onboarding.micPermission.button.denied')
      }}
      onActivate={requestAccess}
      checkGranted={isMicGranted}
      onGranted={handleGranted}
      recoveryLabel={t('onboarding.micPermission.recoveryLabel')}
      onRecover={() => window.omi?.openMicPrivacySettings?.()}
      onContinue={onContinue}
      onBack={onBack}
      onSkip={onSkip}
    />
  )
}
