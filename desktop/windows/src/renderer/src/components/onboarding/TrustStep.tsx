import { Monitor, Mic, Sparkles, type LucideIcon } from 'lucide-react'
import { StepScaffold } from './StepScaffold'
import { useTranslation } from '../../i18n'

type TrustStepProps = {
  stepIndex: number
  totalSteps: number
  onContinue: () => void
  onBack: () => void
}

// The macOS desktop app's "Read the source code" button opens the public repo.
const SOURCE_URL = 'https://github.com/BasedHardware/omi'

const PERMISSION_KEYS: { icon: LucideIcon; titleKey: string; detailKey: string }[] = [
  {
    icon: Monitor,
    titleKey: 'onboarding.trust.permissions.screen.title',
    detailKey: 'onboarding.trust.permissions.screen.detail'
  },
  {
    icon: Mic,
    titleKey: 'onboarding.trust.permissions.microphone.title',
    detailKey: 'onboarding.trust.permissions.microphone.detail'
  },
  {
    icon: Sparkles,
    titleKey: 'onboarding.trust.permissions.automation.title',
    detailKey: 'onboarding.trust.permissions.automation.detail'
  }
]

export function TrustStep({
  stepIndex,
  totalSteps,
  onContinue,
  onBack
}: TrustStepProps): React.JSX.Element {
  const { t } = useTranslation()
  return (
    <StepScaffold
      stepIndex={stepIndex}
      totalSteps={totalSteps}
      eyebrow={t('onboarding.trust.eyebrow')}
      title={t('onboarding.trust.title')}
    >
      <div className="w-full">
        <p className="text-center text-sm leading-relaxed text-white">
          {t('onboarding.trust.intro')}
        </p>

        <div className="mt-6 flex flex-col gap-3">
          {PERMISSION_KEYS.map(({ icon: Icon, titleKey, detailKey }) => (
            <div
              key={titleKey}
              className="flex w-full items-center gap-4 rounded-xl bg-white/[0.06] px-5 py-3 text-left"
            >
              <Icon className="h-6 w-6 shrink-0 text-white/80" strokeWidth={1.75} />
              <div>
                <p className="text-sm font-semibold text-white">{t(titleKey)}</p>
                <p className="mt-0.5 text-xs text-white/60">{t(detailKey)}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-6 flex items-center justify-center gap-2.5">
          <button
            type="button"
            onClick={onBack}
            className="rounded-lg bg-black px-5 py-2 text-sm font-medium text-white ring-1 ring-white/15 transition-colors hover:bg-white/5"
          >
            {t('onboarding.trust.back')}
          </button>
          <button
            type="button"
            onClick={onContinue}
            className="rounded-lg bg-white px-5 py-2 text-sm font-medium text-black transition-opacity hover:opacity-90"
          >
            {t('onboarding.trust.continue')}
          </button>
          <button
            type="button"
            onClick={() => window.open(SOURCE_URL)}
            className="rounded-lg bg-black px-5 py-2 text-sm font-medium text-white ring-1 ring-white/15 transition-colors hover:bg-white/5"
          >
            {t('onboarding.trust.readSource')}
          </button>
        </div>
      </div>
    </StepScaffold>
  )
}
