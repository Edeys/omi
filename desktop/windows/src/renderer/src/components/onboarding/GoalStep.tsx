import { useState } from 'react'
import { Sparkles } from 'lucide-react'
import { StepScaffold } from './StepScaffold'
import { generateGoal } from '../../lib/goals'
import { useTranslation } from '../../i18n'

type GoalStepProps = {
  stepIndex: number
  totalSteps: number
  aside?: React.ReactNode
  /** App names already in the onboarding brain map — used to personalize the
   *  AI-generated goal. */
  apps: string[]
  /** Commit the chosen goal text and advance. */
  onContinue: (goal: string) => void
  onSkip?: () => void
}

// The two starter goals offered on the desktop app. They have no number, so the
// backend sync falls back to a target_value of 1 (see parseTargetValue).
// Keys are translated via i18n; keep English values for analytics/exact match.
const SUGGESTED_KEYS = ['onboarding.goal.suggested1', 'onboarding.goal.suggested2'] as const
const SUGGESTED_EN = [
  'Be more productive and focused every day',
  'Make meaningful progress on my projects'
]

// A goal card: rounded panel matching the permission-step cards. `selected`
// flips it to the solid-white highlight just before advancing.
function GoalCard({
  label,
  selected,
  onClick,
  className = ''
}: {
  label: string
  selected: boolean
  onClick: () => void
  className?: string
}): React.JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        'rounded-xl px-5 py-4 text-left text-sm font-medium transition-colors ' +
        (selected ? 'bg-white text-black' : 'bg-white/[0.06] text-white/80 hover:bg-white/[0.1]') +
        ' ' +
        className
      }
    >
      {label}
    </button>
  )
}

export function GoalStep({
  stepIndex,
  totalSteps,
  aside,
  apps,
  onContinue,
  onSkip
}: GoalStepProps): React.JSX.Element {
  const { t } = useTranslation()
  // 'choose'   — the four buttons.
  // 'typing'   — the editable textarea (Type my own / review an AI draft).
  // The AI button toggles `generating` while it waits on the LLM.
  const [mode, setMode] = useState<'choose' | 'typing'>('choose')
  const [draft, setDraft] = useState('')
  const [generating, setGenerating] = useState(false)
  // Which suggested card is briefly highlighted before we advance.
  const [picked, setPicked] = useState<string | null>(null)

  const commit = (goal: string): void => {
    const text = goal.trim()
    if (!text) return
    onContinue(text)
  }

  const pickSuggested = (goal: string): void => {
    if (picked) return
    setPicked(goal)
    // Brief highlight before advancing, mirroring the "How did you hear" step.
    setTimeout(() => commit(goal), 250)
  }

  const runGenerate = async (): Promise<void> => {
    if (generating) return
    setGenerating(true)
    try {
      const goal = await generateGoal(apps)
      // Drop the suggestion into the editable textarea so the user can review
      // and tweak it before committing, rather than auto-advancing on it.
      setDraft(goal)
      setMode('typing')
    } catch {
      // If generation fails, just open an empty box so the user can type.
      setMode('typing')
    } finally {
      setGenerating(false)
    }
  }

  return (
    <StepScaffold
      stepIndex={stepIndex}
      totalSteps={totalSteps}
      eyebrow={t('onboarding.goal.eyebrow')}
      title={t('onboarding.goal.title')}
      subtitle={t('onboarding.goal.subtitle')}
      align="left"
      aside={aside}
      onSkip={onSkip}
    >
      {mode === 'choose' ? (
        <div className="flex w-full flex-col gap-2.5">
          <div className="grid grid-cols-2 gap-2.5">
            {SUGGESTED_KEYS.map((key, idx) => (
              <GoalCard
                key={key}
                label={t(key)}
                selected={picked === SUGGESTED_EN[idx]}
                onClick={() => pickSuggested(SUGGESTED_EN[idx])}
              />
            ))}
          </div>
          <GoalCard
            label={t('onboarding.goal.typeMyOwn')}
            selected={false}
            onClick={() => {
              setDraft('')
              setMode('typing')
            }}
            className="text-center"
          />
          <button
            type="button"
            onClick={() => void runGenerate()}
            disabled={generating}
            className={
              'flex items-center justify-center gap-2 rounded-xl px-5 py-4 text-center text-sm font-medium transition-colors ' +
              (generating
                ? 'cursor-wait bg-white/[0.06] text-white/50'
                : 'bg-white/[0.06] text-white/80 hover:bg-white/[0.1]')
            }
          >
            <Sparkles className="h-4 w-4" />
            {generating ? t('onboarding.goal.generating') : t('onboarding.goal.generate')}
          </button>
        </div>
      ) : (
        <div className="flex w-full flex-col gap-3">
          <textarea
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={3}
            placeholder={t('onboarding.goal.placeholder')}
            className="w-full resize-none rounded-xl bg-white/[0.06] px-5 py-4 text-sm text-white/90 placeholder:text-white/30 focus:bg-white/[0.1] focus:outline-none"
          />
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMode('choose')}
              className="rounded-xl bg-white/[0.06] px-5 py-3 text-sm font-medium text-white/70 transition-colors hover:bg-white/[0.1]"
            >
              {t('onboarding.goal.back')}
            </button>
            <button
              type="button"
              onClick={() => commit(draft)}
              disabled={!draft.trim()}
              className="rounded-xl bg-white px-8 py-3 text-sm font-medium text-black transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {t('onboarding.goal.continue')}
            </button>
          </div>
        </div>
      )}
    </StepScaffold>
  )
}
