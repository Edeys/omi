import { useState } from 'react'
import { toast } from '../../../../lib/toast'
import { useTranslation } from '../../../../i18n'
import { toastImportTally } from '../../../../lib/importToast'
import { useMemories } from '../../../../hooks/useMemories'
import { readAndExtractStickyNotes, importStickyMemories } from '../../../../lib/stickyNotesImport'
import { ConnectorRow, PillButton } from './ConnectorRow'
import { ConnectorBrandMark } from './ConnectorBrandMark'
import { MemoryPreviewList } from './MemoryPreviewList'

// Sticky Notes import — the Windows-native stand-in for Mac's Apple Notes import
// connector. Reads local Sticky Notes, synthesizes durable memories, previews them
// for review, then writes on confirm. All logic is shared with Settings →
// Integrations via lib/stickyNotesImport.ts.

export function StickyNotesConnector(): React.JSX.Element {
  const { t } = useTranslation()
  const { memories, refresh } = useMemories()
  const [reading, setReading] = useState(false)
  const [importing, setImporting] = useState(false)
  const [preview, setPreview] = useState<{ memories: string[]; profile: string } | null>(null)

  const read = async (): Promise<void> => {
    if (reading || importing) return
    setReading(true)
    setPreview(null)
    try {
      const outcome = await readAndExtractStickyNotes(memories.map((m) => m.content))
      if (outcome.status === 'unavailable')
        toast(t('home.connections.noStickyFound'), { tone: 'warn' })
      else if (outcome.status === 'error')
        toast(t('home.connections.stickyCouldNotRead'), { tone: 'error', body: outcome.error })
      else if (outcome.status === 'empty')
        toast(
          outcome.reason === 'no-notes'
            ? t('home.connections.noStickyText')
            : t('home.connections.noNewStickyMemories'),
          { tone: 'warn' }
        )
      else setPreview({ memories: outcome.memories, profile: outcome.profile })
    } catch (e) {
      toast(t('home.connections.stickyCouldNotRead'), { tone: 'error', body: (e as Error).message })
    } finally {
      setReading(false)
    }
  }

  const runImport = async (): Promise<void> => {
    if (!preview || preview.memories.length === 0 || importing) return
    setImporting(true)
    const tally = await importStickyMemories(preview.memories, preview.profile)
    setImporting(false)
    toastImportTally(tally)
    if (tally.ok > 0) await refresh()
    if (!tally.failed) setPreview(null)
  }

  const count = preview?.memories.length ?? 0

  return (
    <ConnectorRow
      iconNode={<ConnectorBrandMark brand="sticky" />}
      title="Sticky Notes"
      description="Turn your Sticky Notes into durable memories — they never leave your PC."
      action={
        count > 0 ? (
          <PillButton tone="primary" onClick={runImport} disabled={importing}>
            {importing ? 'Importing…' : `Import ${count}`}
          </PillButton>
        ) : (
          <PillButton tone="primary" onClick={read} disabled={reading}>
            {reading ? 'Reading…' : 'Read notes'}
          </PillButton>
        )
      }
    >
      {preview && <MemoryPreviewList profile={preview.profile} memories={preview.memories} />}
    </ConnectorRow>
  )
}
