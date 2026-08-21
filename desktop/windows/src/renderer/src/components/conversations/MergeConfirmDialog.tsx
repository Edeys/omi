import { useState } from 'react'
import { Loader2, Merge } from 'lucide-react'
import { ModalShell } from './ModalShell'
import { useTranslation } from '../../i18n'

// Confirm a multi-select merge. Copy matches the Mac alert verbatim. Merge is
// fire-and-forget on the backend (returns {status:'merging'}, no new id) — the
// caller refetches the list after onConfirm resolves.
export function MergeConfirmDialog({
  // i18n inside
  count,
  onCancel,
  onConfirm
}: {
  count: number
  onCancel: () => void
  onConfirm: () => Promise<void>
}): React.JSX.Element {
  const { t } = useTranslation()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const confirm = async (): Promise<void> => {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      await onConfirm()
    } catch (e) {
      setError((e as Error).message || t('conversations.mergeDialog.couldNotMerge'))
      setBusy(false)
    }
  }

  return (
    <ModalShell onClose={onCancel} labelledBy="merge-title">
      <h2 id="merge-title" className="text-lg font-semibold text-text-primary">
        {t('conversations.mergeDialog.title', { count })}
      </h2>
      <p className="mt-2 text-sm leading-relaxed text-text-tertiary">
        {t('conversations.mergeDialog.description')}
      </p>
      {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
      <div className="mt-6 flex justify-end gap-2">
        <button onClick={onCancel} disabled={busy} className="btn-ghost">
          {t('conversations.mergeDialog.cancel')}
        </button>
        <button onClick={() => void confirm()} disabled={busy} className="btn-primary">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Merge className="h-4 w-4" />}
          {t('conversations.mergeDialog.merge')}
        </button>
      </div>
    </ModalShell>
  )
}
