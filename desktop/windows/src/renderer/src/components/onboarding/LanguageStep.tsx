import { useState } from 'react'
import { StepScaffold } from './StepScaffold'
import { useTranslation } from '../../i18n'

type LanguageStepProps = {
  stepIndex: number
  totalSteps: number
  initialValue: string
  onContinue: (language: string) => void
  onBack: () => void
  aside?: React.ReactNode
}

export function LanguageStep({
  stepIndex,
  totalSteps,
  initialValue,
  onContinue,
  onBack,
  aside
}: LanguageStepProps): React.JSX.Element {
  const { t } = useTranslation()
  const [mode, setMode] = useState<'english' | 'other'>(
    initialValue && initialValue !== 'en' ? 'other' : 'english'
  )
  const [other, setOther] = useState(initialValue && initialValue !== 'en' ? initialValue : '')
  const trimmed = other.trim()

  return (
    <StepScaffold
      stepIndex={stepIndex}
      totalSteps={totalSteps}
      eyebrow={t('onboarding.language.eyebrow')}
      title={t('onboarding.language.title')}
      align="left"
      onBack={onBack}
      aside={aside}
    >
      <div className="flex gap-3">
        <button
          type="button"
          onClick={() => onContinue('en')}
          className={
            'rounded-xl px-8 py-3 text-sm font-medium ' +
            (mode === 'english'
              ? 'bg-white text-black'
              : 'bg-white/[0.06] text-white/80 hover:bg-white/[0.1]')
          }
        >
          {t('onboarding.language.english')}
        </button>
        <button
          type="button"
          onClick={() => setMode('other')}
          className={
            'rounded-xl px-8 py-3 text-sm font-medium ' +
            (mode === 'other'
              ? 'bg-white text-black'
              : 'bg-white/[0.06] text-white/80 hover:bg-white/[0.1]')
          }
        >
          {t('onboarding.language.other')}
        </button>
      </div>

      {mode === 'other' && (
        <div className="mt-4 flex w-full flex-col items-start gap-3">
          <input
            autoFocus
            value={other}
            onChange={(e) => setOther(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && trimmed.length > 0) onContinue(trimmed)
            }}
            placeholder={t('onboarding.language.otherPlaceholder')}
            className="glass-subtle w-72 rounded-lg px-4 py-3 text-sm text-white/90 placeholder:text-white/30 focus:outline-none focus:ring-1 focus:ring-white/30"
          />
          <button
            type="button"
            onClick={() => onContinue(trimmed)}
            disabled={trimmed.length === 0}
            className="rounded-xl bg-white px-8 py-3 text-sm font-medium text-black transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t('onboarding.language.saveLanguage')}
          </button>
        </div>
      )}
    </StepScaffold>
  )
}
