import { useState } from 'react'
import { StepScaffold } from './StepScaffold'
import { useTranslation } from '../../i18n'

type NameStepProps = {
  stepIndex: number
  totalSteps: number
  initialValue: string
  onContinue: (name: string) => void
  onBack?: () => void
}

export function NameStep({
  stepIndex,
  totalSteps,
  initialValue,
  onContinue,
  onBack
}: NameStepProps): React.JSX.Element {
  const { t } = useTranslation()
  const [name, setName] = useState(initialValue)
  const trimmed = name.trim()

  return (
    <StepScaffold
      stepIndex={stepIndex}
      totalSteps={totalSteps}
      eyebrow={t('onboarding.name.eyebrow')}
      title={t('onboarding.name.title')}
      continueDisabled={trimmed.length === 0}
      onContinue={() => onContinue(trimmed)}
      onBack={onBack}
    >
      <input
        autoFocus
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && trimmed.length > 0) onContinue(trimmed)
        }}
        placeholder={t('onboarding.name.placeholder')}
        className="glass-subtle w-64 rounded-lg px-4 py-3 text-center text-sm text-white/90 placeholder:text-white/30 focus:outline-none focus:ring-1 focus:ring-white/30"
      />
    </StepScaffold>
  )
}
