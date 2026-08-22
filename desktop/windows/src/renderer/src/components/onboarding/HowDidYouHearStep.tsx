import { useState } from 'react'
import { StepScaffold } from './StepScaffold'
import { useTranslation } from '../../i18n'

type HowDidYouHearStepProps = {
  stepIndex: number
  totalSteps: number
  onContinue: (source: string) => void
  onBack: () => void
  aside?: React.ReactNode
}

// Same set the macOS desktop app offers (canonical casing matches the values it
// reports to PostHog), in the order requested for the Windows wizard.
// Display labels are translated; the underlying value sent to analytics stays English.
const SOURCE_KEYS: { value: string; labelKey: string }[] = [
  { value: 'Other', labelKey: 'onboarding.howDidYouHear.sources.other' },
  { value: 'Colleague', labelKey: 'onboarding.howDidYouHear.sources.colleague' },
  { value: 'Product Hunt', labelKey: 'onboarding.howDidYouHear.sources.productHunt' },
  { value: 'Article', labelKey: 'onboarding.howDidYouHear.sources.article' },
  { value: 'Friend', labelKey: 'onboarding.howDidYouHear.sources.friend' },
  { value: 'Event', labelKey: 'onboarding.howDidYouHear.sources.event' },
  { value: 'AI chat', labelKey: 'onboarding.howDidYouHear.sources.aiChat' },
  { value: 'YouTube', labelKey: 'onboarding.howDidYouHear.sources.youtube' },
  { value: 'Search engine', labelKey: 'onboarding.howDidYouHear.sources.searchEngine' },
  { value: 'Newsletter', labelKey: 'onboarding.howDidYouHear.sources.newsletter' },
  { value: 'Podcast', labelKey: 'onboarding.howDidYouHear.sources.podcast' },
  { value: 'Social media', labelKey: 'onboarding.howDidYouHear.sources.socialMedia' }
]

export function HowDidYouHearStep({
  stepIndex,
  totalSteps,
  onContinue,
  onBack,
  aside
}: HowDidYouHearStepProps): React.JSX.Element {
  const { t } = useTranslation()
  const [selected, setSelected] = useState<string | null>(null)

  const pick = (source: string): void => {
    if (selected) return
    setSelected(source)
    // Brief highlight before advancing, mirroring the desktop app's 0.25s delay.
    setTimeout(() => onContinue(source), 250)
  }

  return (
    <StepScaffold
      stepIndex={stepIndex}
      totalSteps={totalSteps}
      eyebrow={t('onboarding.howDidYouHear.eyebrow')}
      title={t('onboarding.howDidYouHear.title')}
      align="left"
      onBack={onBack}
      aside={aside}
    >
      <div className="flex flex-wrap gap-2.5">
        {SOURCE_KEYS.map(({ value, labelKey }) => (
          <button
            key={value}
            type="button"
            onClick={() => pick(value)}
            className={
              'rounded-xl px-5 py-2.5 text-sm font-medium ' +
              (selected === value
                ? 'bg-white text-black'
                : 'bg-white/[0.06] text-white/80 hover:bg-white/[0.1]')
            }
          >
            {t(labelKey)}
          </button>
        ))}
      </div>
    </StepScaffold>
  )
}
