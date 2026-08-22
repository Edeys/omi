import { useState } from 'react'
import { DollarSign, CheckCircle2, Info } from 'lucide-react'
import { BillingCard } from './BillingCard'
import { useTranslation } from '../../../i18n'
import type { OverageInfoResponse } from '../../../lib/omiApi.generated'

/**
 * Overage card (AccountBilling) — shown only for overage plans. Icon/title flip
 * on whether the user is over their included limit; an expandable explainer
 * mirrors Mac's sheet, including the current-cycle number rows.
 */
export function OverageCard(props: { overage: OverageInfoResponse }): React.JSX.Element {
  const { overage } = props
  const [open, setOpen] = useState(false)
  const { t } = useTranslation()
  const excess = overage.excess_questions ?? 0
  const included = overage.included_questions ?? 0
  const over = excess > 0

  const body = over
    ? t('settings.planUsage.overageBodyOverage', {
        excess,
        included,
        plural: excess === 1 ? '' : 's'
      })
    : t('settings.planUsage.overageBodyNoOverage', {
        included,
        percent: Math.round(overage.markup_percent)
      })

  return (
    <BillingCard
      icon={over ? DollarSign : CheckCircle2}
      iconTone={over ? 'amber' : 'green'}
      title={over ? t('settings.planUsage.overageTitle') : t('settings.planUsage.overageNoOverage')}
      subtitle={body}
      trailing={
        over ? (
          <span className="tnum text-sm font-semibold text-amber-300">
            ${(overage.overage_usd ?? 0).toFixed(2)}
          </span>
        ) : undefined
      }
    >
      <button onClick={() => setOpen((o) => !o)} className="btn-ghost">
        <Info className="h-4 w-4" />
        {overage.explainer_title || t('settings.planUsage.overageExplainer')}
      </button>
      {open ? (
        <div className="mt-3 space-y-3">
          <p className="text-sm leading-relaxed text-white/65">{overage.explainer_body}</p>
          <dl className="space-y-1.5 border-t border-white/[0.06] pt-3 text-sm">
            <CycleRow
              label={t('settings.planUsage.overageQuestionsUsed')}
              value={String(overage.used_questions ?? 0)}
            />
            <CycleRow label={t('settings.planUsage.overageIncluded')} value={String(included)} />
            <CycleRow label={t('settings.planUsage.overageOverLimit')} value={String(excess)} />
            <CycleRow
              label={t('settings.planUsage.overageRealCost')}
              value={`$${(overage.real_cost_usd ?? 0).toFixed(2)}`}
            />
            <CycleRow
              label={t('settings.planUsage.overageMarkup')}
              value={`${Math.round(overage.markup_percent)}%`}
            />
            <CycleRow
              label={t('settings.planUsage.overageToBill')}
              value={`$${(overage.overage_usd ?? 0).toFixed(2)}`}
              emphasized
            />
          </dl>
        </div>
      ) : null}
    </BillingCard>
  )
}

function CycleRow(props: {
  label: string
  value: string
  emphasized?: boolean
}): React.JSX.Element {
  return (
    <div className="flex items-center justify-between">
      <dt className="text-white/55">{props.label}</dt>
      <dd className={props.emphasized ? 'tnum font-semibold text-amber-300' : 'tnum text-white/80'}>
        {props.value}
      </dd>
    </div>
  )
}
