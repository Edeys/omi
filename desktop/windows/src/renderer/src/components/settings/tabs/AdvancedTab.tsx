import { useEffect, useState } from 'react'
import { Download, Upload, Wrench, FolderSearch, Network, RotateCcw } from 'lucide-react'
import { omiApi } from '../../../lib/apiClient'
import { toast } from '../../../lib/toast'
import { type MemorySource } from '../../../lib/memoryExtract'
import {
  extractPasteMemories,
  importPasteMemories,
  toastForExtractResult
} from '../../../lib/pasteImport'
import { toastImportTally } from '../../../lib/importToast'
import { buildLocalGraph } from '../../../lib/kgSynthesis'
import {
  summarizeMemories,
  appIndexMemoryIds,
  type MemoryBreakdown
} from '../../../lib/memoryCleanup'
import { fetchAllMemories } from '../../../lib/memoriesBulk'
import { runMemoryExport } from '../../../lib/memoryExport'
import { useMemories, type Memory } from '../../../hooks/useMemories'
import { resetOnboarding } from '../../../lib/preferences'
import { SettingRow } from '../SettingRow'
import { IntegrationsTab } from './IntegrationsTab'
import { DeveloperKeysSection } from './DeveloperKeysSection'
import { AiProfileCard } from './AiProfileCard'
import { useTranslation } from '../../../i18n'
import type { ExportMemory, FileIndexStatus, LocalKGStatus } from '../../../../../shared/types'

export function AdvancedTab(): React.JSX.Element {
  const { memories, refresh } = useMemories()
  const { t } = useTranslation()

  // --- File indexing ---
  const [fileIndex, setFileIndex] = useState<FileIndexStatus | null>(null)
  const [scanning, setScanning] = useState(false)
  useEffect(() => {
    window.omi
      .indexFilesStatus()
      .then(setFileIndex)
      .catch(() => setFileIndex(null))
  }, [])
  const rescan = async (): Promise<void> => {
    if (scanning) return
    setScanning(true)
    try {
      setFileIndex(await window.omi.indexFilesScan())
      toast(t('settings.advanced.fileIndexUpdated'), { tone: 'success' })
      void buildLocalGraph().catch(() => {})
    } catch (e) {
      toast(t('settings.advanced.fileIndexFailed'), { tone: 'error', body: (e as Error).message })
    } finally {
      setScanning(false)
    }
  }

  // --- Knowledge graph ---
  const [kgStatus, setKgStatus] = useState<LocalKGStatus | null>(null)
  const [rebuildingKg, setRebuildingKg] = useState(false)
  useEffect(() => {
    window.omi
      .kgStatus()
      .then(setKgStatus)
      .catch(() => setKgStatus(null))
  }, [])
  const rebuildKg = async (): Promise<void> => {
    if (rebuildingKg) return
    setRebuildingKg(true)
    try {
      setKgStatus(await buildLocalGraph())
      toast(t('settings.advanced.kgRebuilt'), { tone: 'success' })
    } catch (e) {
      toast(t('settings.advanced.kgRebuildFailed'), { tone: 'error', body: (e as Error).message })
    } finally {
      setRebuildingKg(false)
    }
  }

  // --- Import memories ---
  const [dump, setDump] = useState('')
  const [source, setSource] = useState<MemorySource>('chatgpt')
  const [parsed, setParsed] = useState<string[] | null>(null)
  const [profile, setProfile] = useState('')
  const [extracting, setExtracting] = useState(false)
  const [importing, setImporting] = useState(false)

  const extractDump = async (): Promise<void> => {
    if (extracting) return
    setExtracting(true)
    setProfile('')
    try {
      const r = await extractPasteMemories(
        dump,
        source,
        memories.map((m) => m.content)
      )
      setParsed(r.memories)
      setProfile(r.profile)
      toastForExtractResult(r)
    } catch (e) {
      toast(t('settings.advanced.extractFailed'), { tone: 'error', body: (e as Error).message })
    } finally {
      setExtracting(false)
    }
  }

  const importMemories = async (): Promise<void> => {
    if (!parsed || parsed.length === 0 || importing) return
    setImporting(true)
    const tally = await importPasteMemories(parsed)
    setImporting(false)
    toastImportTally(tally)
    if (tally.ok > 0) await refresh()
    if (!tally.failed) {
      setDump('')
      setParsed(null)
      setProfile('')
    }
  }

  // --- Export memories ---
  const [notionToken, setNotionToken] = useState('')
  const [notionPage, setNotionPage] = useState('')
  const [exporting, setExporting] = useState(false)
  const toExportMemories = (): ExportMemory[] =>
    memories.map((m) => ({
      content: m.content,
      category: m.category ?? null,
      createdAt: m.created_at
    }))

  const runExport = async (target: 'obsidian' | 'file' | 'notion'): Promise<void> => {
    if (exporting) return
    if (memories.length === 0) {
      toast(t('settings.advanced.noMemoriesToExport'), { tone: 'warn' })
      return
    }
    if (target === 'notion' && (!notionToken.trim() || !notionPage.trim())) {
      toast(t('settings.advanced.notionMissing'), { tone: 'warn' })
      return
    }
    setExporting(true)
    try {
      const r = await runMemoryExport(
        target,
        toExportMemories(),
        target === 'notion'
          ? { token: notionToken.trim(), parentPageId: notionPage.trim() }
          : undefined
      )
      if (!r.canceled) {
        toast(`Exported ${r.count} memor${r.count === 1 ? 'y' : 'ies'}`, {
          tone: 'success',
          body: r.location
        })
      }
    } catch (e) {
      toast(t('settings.advanced.exportFailed'), { tone: 'error', body: (e as Error).message })
    } finally {
      setExporting(false)
    }
  }

  // --- Memory maintenance ---
  const [memBreakdown, setMemBreakdown] = useState<MemoryBreakdown | null>(null)
  const [memAllMemories, setMemAllMemories] = useState<Memory[]>([])
  const [memAuditing, setMemAuditing] = useState(false)
  const [memDeleting, setMemDeleting] = useState(false)
  const [memDeleteProgress, setMemDeleteProgress] = useState(0)

  const auditMemories = async (): Promise<void> => {
    if (memAuditing || memDeleting) return
    setMemAuditing(true)
    try {
      const all = await fetchAllMemories()
      setMemAllMemories(all)
      setMemBreakdown(summarizeMemories(all))
    } catch (e) {
      toast(t('settings.advanced.couldNotLoadMemories'), {
        tone: 'error',
        body: (e as Error).message
      })
    } finally {
      setMemAuditing(false)
    }
  }

  const deleteAppIndexMemories = async (): Promise<void> => {
    const ids = appIndexMemoryIds(memAllMemories)
    if (ids.length === 0 || memDeleting) return
    if (
      !window.confirm(
        `Permanently delete ${ids.length} app/file-index memories? This cannot be undone.`
      )
    )
      return
    setMemDeleting(true)
    setMemDeleteProgress(0)
    const sleep = (ms: number): Promise<void> => new Promise((r) => setTimeout(r, ms))
    let deleted = 0
    let failed = 0
    let firstError = ''
    let paceMs = 1100

    const deleteIdPaced = async (id: string): Promise<'ok' | 'gone' | 'fail'> => {
      for (let attempt = 0; attempt < 30; attempt++) {
        try {
          await omiApi.delete(`/v3/memories/${id}`, { ...({ __noRetry: true } as object) })
          return 'ok'
        } catch (e) {
          const resp = (e as { response?: { status?: number; headers?: Record<string, string> } })
            .response
          const status = resp?.status
          if (status === 404) return 'gone'
          if (status === 429) {
            paceMs = 1100
            const ra = Number(resp?.headers?.['retry-after'])
            await sleep(
              Number.isFinite(ra) && ra > 0 ? ra * 1000 : Math.min(3000 * 1.6 ** attempt, 60_000)
            )
            continue
          }
          if (!firstError) firstError = status ? `HTTP ${status}` : (e as Error).message
          return 'fail'
        }
      }
      return 'fail'
    }

    try {
      for (let i = 0; i < ids.length; i++) {
        const r = await deleteIdPaced(ids[i])
        if (r === 'ok' || r === 'gone') deleted++
        else failed++
        if (i % 10 === 0 || i === ids.length - 1) setMemDeleteProgress(deleted)
        if (paceMs) await sleep(paceMs)
      }
      toast(`Deleted ${deleted} of ${ids.length} memories`, {
        tone: failed ? 'warn' : 'success',
        body: failed
          ? `${failed} failed${firstError ? ` — ${firstError}` : ''}. Analyze again to retry.`
          : undefined
      })
    } catch (e) {
      toast('Delete failed', { tone: 'error', body: (e as Error).message })
    } finally {
      setMemDeleting(false)
    }
    await refresh()
    await auditMemories()
  }

  const replayOnboarding = (): void => {
    resetOnboarding()
    window.location.reload()
  }

  return (
    <>
      <SettingRow
        icon={Download}
        title={t('settings.advanced.importTitle')}
        subtitle={t('settings.advanced.importSubtitle')}
        keywords="import chatgpt claude memories paste extract"
      >
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <span className="text-sm text-text-tertiary">
              {t('settings.advanced.exportedFrom')}
            </span>
            {(['chatgpt', 'claude'] as const).map((s) => (
              <button
                key={s}
                onClick={() => setSource(s)}
                className={`rounded-md px-3 py-1 text-sm ${source === s ? 'btn-primary' : 'btn-ghost'}`}
              >
                {s === 'chatgpt' ? t('settings.advanced.chatgpt') : t('settings.advanced.claude')}
              </button>
            ))}
          </div>
          <textarea
            value={dump}
            onChange={(e) => {
              setDump(e.target.value)
              setParsed(null)
              setProfile('')
            }}
            rows={5}
            placeholder={t('settings.advanced.pastePlaceholder')}
            className="input-field resize-none"
          />
          <div className="flex items-center gap-2">
            <button
              onClick={extractDump}
              disabled={!dump.trim() || extracting || importing}
              className="btn-ghost disabled:opacity-40"
            >
              {extracting ? t('settings.advanced.extracting') : t('settings.advanced.extract')}
            </button>
            {parsed && parsed.length > 0 && (
              <button
                onClick={importMemories}
                disabled={importing}
                className="btn-primary px-4 py-2 disabled:opacity-40"
              >
                {importing
                  ? t('settings.advanced.importing')
                  : t('settings.advanced.importButton', {
                      count: parsed.length,
                      plural: parsed.length === 1 ? 'y' : 'ies'
                    })}
              </button>
            )}
          </div>
          {profile && (
            <p className="glass-subtle rounded-lg px-4 py-3 text-sm italic text-text-tertiary">
              {profile}
            </p>
          )}
          {parsed && parsed.length > 0 && (
            <ul className="glass-subtle max-h-40 overflow-y-auto rounded-lg px-4 py-3 text-sm text-text-tertiary">
              {parsed.map((m, i) => (
                <li key={i} className="py-0.5">
                  • {m}
                </li>
              ))}
            </ul>
          )}
        </div>
      </SettingRow>

      <SettingRow
        icon={Upload}
        title={t('settings.advanced.exportTitle')}
        subtitle={t('settings.advanced.exportSubtitle', {
          count: memories.length,
          plural: memories.length === 1 ? 'y' : 'ies'
        })}
        keywords="export obsidian notion file markdown"
      >
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => runExport('obsidian')}
              disabled={exporting}
              className="btn-ghost disabled:opacity-40"
            >
              {t('settings.advanced.obsidianVault')}
            </button>
            <button
              onClick={() => runExport('file')}
              disabled={exporting}
              className="btn-ghost disabled:opacity-40"
            >
              {t('settings.advanced.plainFile')}
            </button>
          </div>
          <div className="border-t border-white/5 pt-3">
            <p className="mb-2 text-sm text-text-tertiary">{t('settings.advanced.notionHelp')}</p>
            <input
              value={notionToken}
              onChange={(e) => setNotionToken(e.target.value)}
              placeholder={t('settings.advanced.notionTokenPlaceholder')}
              className="glass-subtle mb-2 w-full rounded-lg px-4 py-3 text-sm text-text-secondary focus:outline-none"
            />
            <input
              value={notionPage}
              onChange={(e) => setNotionPage(e.target.value)}
              placeholder={t('settings.advanced.notionPagePlaceholder')}
              className="glass-subtle mb-2 w-full rounded-lg px-4 py-3 text-sm text-text-secondary focus:outline-none"
            />
            <button
              onClick={() => runExport('notion')}
              disabled={exporting}
              className="btn-ghost disabled:opacity-40"
            >
              {exporting ? t('settings.advanced.exporting') : t('settings.advanced.exportToNotion')}
            </button>
          </div>
        </div>
      </SettingRow>

      <SettingRow
        icon={Wrench}
        title={t('settings.advanced.maintenanceTitle')}
        subtitle={t('settings.advanced.maintenanceSubtitle')}
        keywords="maintenance cleanup delete app file index memories audit"
      >
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <button
              onClick={auditMemories}
              disabled={memAuditing || memDeleting}
              className="btn-ghost disabled:opacity-40"
            >
              {memAuditing ? t('settings.advanced.analyzing') : t('settings.advanced.analyze')}
            </button>
            {memBreakdown && memBreakdown.appIndexCount > 0 && (
              <button
                onClick={deleteAppIndexMemories}
                disabled={memDeleting || memAuditing}
                className="btn-primary px-4 py-2 disabled:opacity-40"
              >
                {memDeleting
                  ? t('settings.advanced.deleting', {
                      done: memDeleteProgress,
                      total: memBreakdown.appIndexCount
                    })
                  : t('settings.advanced.deleteAppMemories', { count: memBreakdown.appIndexCount })}
              </button>
            )}
          </div>
          {memBreakdown && (
            <div className="glass-subtle rounded-lg px-4 py-3 text-sm text-text-tertiary">
              <p className="mb-2 text-text-secondary">
                {t('settings.advanced.totalMemories', {
                  total: memBreakdown.total,
                  count: memBreakdown.appIndexCount
                })}
              </p>
              {memBreakdown.appIndexCount > 0 && (
                <ul className="mb-3 max-h-32 overflow-y-auto">
                  {memBreakdown.appIndexSamples.map((s, i) => (
                    <li key={i} className="py-0.5">
                      • {s}
                    </li>
                  ))}
                </ul>
              )}
              <p className="mb-1 text-text-secondary">{t('settings.advanced.breakdownTitle')}</p>
              <ul className="max-h-40 overflow-y-auto">
                {memBreakdown.groups.map((g) => (
                  <li key={g.key} className="py-0.5">
                    <span className="text-text-primary">{g.count}</span> — {g.key}
                    {g.samples[0] ? (
                      <span className="opacity-60"> · e.g. “{g.samples[0]}”</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </SettingRow>

      {/* Integrations (Sticky Notes, Google) live under Advanced. */}
      <IntegrationsTab />

      {/* AI profile — Mac renders this as the aiUserProfileSubsection in Advanced. */}
      <AiProfileCard />

      {/* Developer API Keys (BYOK) — Mac renders this as an Advanced subsection. */}
      <DeveloperKeysSection />

      <SettingRow
        icon={FolderSearch}
        title={t('settings.advanced.fileIndexTitle')}
        subtitle={
          fileIndex
            ? t('settings.advanced.fileIndexStatus', {
                count: fileIndex.filesIndexed.toLocaleString(),
                lastRun: fileIndex.lastRunAt
                  ? t('settings.advanced.fileIndexLastRun', {
                      date: new Date(fileIndex.lastRunAt).toLocaleString()
                    })
                  : ''
              })
            : t('settings.advanced.fileIndexSubtitle')
        }
        keywords="file index scan rescan local"
        control={
          <button onClick={rescan} disabled={scanning} className="btn-ghost disabled:opacity-40">
            {scanning
              ? t('settings.advanced.fileIndexIndexing')
              : t('settings.advanced.fileIndexRescan')}
          </button>
        }
      />

      <SettingRow
        icon={Network}
        title={t('settings.advanced.kgTitle')}
        subtitle={
          kgStatus
            ? t('settings.advanced.kgStatus', {
                nodes: kgStatus.nodeCount.toLocaleString(),
                edges: kgStatus.edgeCount.toLocaleString(),
                lastBuilt: kgStatus.lastBuiltAt
                  ? t('settings.advanced.kgLastBuilt', {
                      date: new Date(kgStatus.lastBuiltAt).toLocaleString()
                    })
                  : ''
              })
            : t('settings.advanced.kgSubtitle')
        }
        keywords="knowledge graph rebuild kg nodes"
        control={
          <button
            onClick={rebuildKg}
            disabled={rebuildingKg}
            className="btn-ghost disabled:opacity-40"
          >
            {rebuildingKg ? t('settings.advanced.kgRebuilding') : t('settings.advanced.kgRebuild')}
          </button>
        }
      />

      <SettingRow
        icon={RotateCcw}
        title={t('settings.advanced.onboardingTitle')}
        subtitle={t('settings.advanced.onboardingSubtitle')}
        keywords="onboarding wizard replay reset"
        control={
          <button onClick={replayOnboarding} className="btn-ghost">
            {t('settings.advanced.onboardingReplay')}
          </button>
        }
      />
    </>
  )
}
