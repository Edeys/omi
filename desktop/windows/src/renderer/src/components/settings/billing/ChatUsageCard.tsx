import { MessageSquare } from 'lucide-react'
import { BillingCard } from './BillingCard'
import { UsageBar } from './UsageBar'
import { chatQuotaView, quotaResetText } from '../../../lib/billing'
import { useTranslation } from '../../../i18n'
import type { ChatUsageQuota } from '../../../lib/omiApi.generated'

/**
 * Chat-usage card (AccountBilling): "Usage this month" with the used/limit
 * value, a progress bar (amber at ≥80% or when blocked — never purple), the
 * reset caption, and a below-bar warning when limited or close to the limit.
 */
export function ChatUsageCard(props: {
  quota: ChatUsageQuota
  isOveragePlan: boolean
}): React.JSX.Element {
  const vm = chatQuotaView(props.quota, props.isOveragePlan)
  const reset = quotaResetText(vm.resetAt)
  const { t } = useTranslation()

  return (
    <BillingCard
      icon={MessageSquare}
      iconTone={vm.warning ? 'amber' : 'neutral'}
      title={t('settings.planUsage.usageTitle')}
      subtitle={vm.description}
      trailing={
        <span className="tnum text-sm font-semibold text-text-primary">{vm.valueText}</span>
      }
    >
      <UsageBar fraction={vm.fraction} warning={vm.warning} />
      <div className="mt-2 flex items-center justify-between gap-3">
        <span
          className={vm.belowBarWarning ? 'text-xs text-amber-300/90' : 'text-xs text-transparent'}
        >
          {vm.belowBarWarning || ' '}
        </span>
        {reset ? <span className="shrink-0 text-xs text-white/45">{reset}</span> : null}
      </div>
    </BillingCard>
  )
}
