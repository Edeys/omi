import { useCallback, useEffect, useMemo, useState } from 'react'
import { Lightbulb, RefreshCw, Search, Trash2, CheckCheck, ChevronDown } from 'lucide-react'
import { PageHeader } from '../components/layout/PageHeader'
import { EmptyState } from '../components/ui/EmptyState'
import { toast } from '../lib/toast'
import { useTranslation } from '../i18n'
import type { InsightCategory, InsightRecord } from '../../../shared/types'

// Module-level cache so navigating away and back is instant (reads are local-first
// SQLite via IPC; the cache just avoids a skeleton flash on revisit).
const cache = { items: null as InsightRecord[] | null, loaded: false }

// Fixed filter set — the five InsightCategory values plus an "all" pseudo-tab.
const CATEGORY_TABS: { id: 'all' | InsightCategory; labelKey: string }[] = [
  { id: 'all', labelKey: 'insights.tabs.all' },
  { id: 'productivity', labelKey: 'insights.tabs.productivity' },
  { id: 'communication', labelKey: 'insights.tabs.communication' },
  { id: 'learning', labelKey: 'insights.tabs.learning' },
  { id: 'health', labelKey: 'insights.tabs.health' },
  { id: 'other', labelKey: 'insights.tabs.other' }
]

const CATEGORY_LABEL_KEY: Record<InsightCategory, string> = {
  productivity: 'insights.row.categoryProductivity',
  communication: 'insights.row.categoryCommunication',
  learning: 'insights.row.categoryLearning',
  health: 'insights.row.categoryHealth',
  other: 'insights.row.categoryOther'
}

// Compact relative date ("just now", "5m ago", "3h ago", "2d ago"), falling back
// to an absolute date past a week.
function formatWhen(ts: number, t: (k: string, o?: Record<string, unknown>) => string): string {
  const diff = Date.now() - ts
  if (diff < 60_000) return t('insights.time.justNow')
  const mins = Math.floor(diff / 60_000)
  if (mins < 60) return t('insights.time.minutesAgo', { count: mins })
  const hours = Math.floor(mins / 60)
  if (hours < 24) return t('insights.time.hoursAgo', { count: hours })
  const days = Math.floor(hours / 24)
  if (days < 7) return t('insights.time.daysAgo', { count: days })
  const d = new Date(ts)
  const sameYear = d.getFullYear() === new Date().getFullYear()
  return d.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    ...(sameYear ? {} : { year: 'numeric' })
  })
}

export function Insights(): React.JSX.Element {
  const { t } = useTranslation()
  const [items, setItems] = useState<InsightRecord[]>(cache.items ?? [])
  const [loading, setLoading] = useState(!cache.loaded)
  const [refreshing, setRefreshing] = useState(false)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState<'all' | InsightCategory>('all')
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const read = useCallback(async (): Promise<void> => {
    try {
      const list = await window.omi.insightRecent(100)
      cache.items = list
      cache.loaded = true
      setItems(list)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void read()
  }, [read])

  const onRefresh = async (): Promise<void> => {
    if (refreshing) return
    setRefreshing(true)
    await read()
    setRefreshing(false)
  }

  const unreadCount = useMemo(() => items.filter((i) => !i.dismissed).length, [items])
  const subtitle = loading
    ? t('insights.loading')
    : unreadCount > 0
      ? t('insights.subtitleWithUnread', { total: items.length, unread: unreadCount })
      : t('insights.subtitle', { total: items.length })

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    return items.filter((i) => {
      if (category !== 'all' && i.category !== category) return false
      if (!q) return true
      return (
        i.headline.toLowerCase().includes(q) ||
        i.advice.toLowerCase().includes(q) ||
        i.sourceApp.toLowerCase().includes(q)
      )
    })
  }, [items, query, category])

  const dismissOne = async (id: number): Promise<void> => {
    // Optimistic: flag the row read immediately; re-read reconciles on failure.
    setItems((prev) => prev.map((i) => (i.id === id ? { ...i, dismissed: 1 } : i)))
    try {
      await window.omi.insightDismissRecord(id)
    } catch {
      toast(t('insights.toasts.dismissFailed'), { tone: 'error' })
      await read()
    }
  }

  const markAllRead = async (): Promise<void> => {
    if (unreadCount === 0) return
    setItems((prev) => prev.map((i) => ({ ...i, dismissed: 1 })))
    try {
      await window.omi.insightDismissAll()
    } catch {
      toast(t('insights.toasts.markAllFailed'), { tone: 'error' })
      await read()
    }
  }

  const clearHistory = async (): Promise<void> => {
    if (items.length === 0) return
    if (!window.confirm(t('insights.confirmClear'))) return
    setItems([])
    setExpandedId(null)
    try {
      await window.omi.insightClearAll()
    } catch {
      toast(t('insights.toasts.clearFailed'), { tone: 'error' })
      await read()
    }
  }

  const renderRow = (i: InsightRecord): React.JSX.Element => {
    const expanded = expandedId === i.id
    return (
      <li key={i.id} className="surface-card overflow-hidden">
        <button
          onClick={() => setExpandedId(expanded ? null : i.id)}
          className="flex w-full items-start gap-3 p-4 text-left"
        >
          {!i.dismissed && (
            <span
              className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-white/70"
              aria-label={t('insights.row.unreadLabel')}
            />
          )}
          <div className={`min-w-0 flex-1 ${i.dismissed ? 'pl-5' : ''}`}>
            <div className="flex items-center gap-2">
              <span
                className={`truncate text-sm font-medium ${
                  i.dismissed ? 'text-white/60' : 'text-white/90'
                }`}
              >
                {i.headline}
              </span>
            </div>
            <p className="mt-1 text-sm leading-relaxed text-white/60">{i.advice}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-white/40">
              <span className="rounded-md bg-white/5 px-1.5 py-0.5 text-white/55">
                {t(CATEGORY_LABEL_KEY[i.category])}
              </span>
              {i.sourceApp && <span className="truncate">{i.sourceApp}</span>}
              <span>·</span>
              <span>{formatWhen(i.ts, t)}</span>
            </div>
          </div>
          <ChevronDown
            className={`mt-0.5 h-4 w-4 shrink-0 text-white/30 transition-transform ${
              expanded ? 'rotate-180' : ''
            }`}
          />
        </button>

        {expanded && (
          <div className="border-t border-white/10 px-4 py-3">
            {i.reasoning && (
              <div className="mb-3">
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-white/35">
                  {t('insights.row.why')}
                </p>
                <p className="text-sm leading-relaxed text-white/70">{i.reasoning}</p>
              </div>
            )}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-white/40">
              <span>
                {t('insights.row.confidence', { percent: Math.round(i.confidence * 100) })}
              </span>
              <span>{new Date(i.ts).toLocaleString()}</span>
            </div>
            {!i.dismissed && (
              <div className="mt-3">
                <button
                  onClick={() => void dismissOne(i.id)}
                  className="btn-ghost px-3 py-1.5 text-xs"
                >
                  {t('insights.row.dismiss')}
                </button>
              </div>
            )}
          </div>
        )}
      </li>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title={t('insights.title')}
        subtitle={subtitle}
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={markAllRead}
              disabled={unreadCount === 0}
              className="btn-ghost px-3 py-2 disabled:opacity-40"
              title={t('insights.actions.markAllReadTitle')}
            >
              <CheckCheck className="h-4 w-4" />
              {t('insights.actions.markAllRead')}
            </button>
            <button
              onClick={clearHistory}
              disabled={items.length === 0}
              className="btn-ghost px-3 py-2 disabled:opacity-40"
              title={t('insights.actions.clearTitle')}
            >
              <Trash2 className="h-4 w-4" />
              {t('insights.actions.clear')}
            </button>
            <button
              onClick={onRefresh}
              disabled={refreshing || loading}
              className="btn-ghost px-3 py-2 disabled:opacity-50"
              title={t('insights.actions.refreshTitle')}
            >
              <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            </button>
          </div>
        }
      />
      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6 lg:px-10 lg:py-8">
        {!loading && items.length > 0 && (
          <div className="mx-auto mb-5 flex max-w-3xl flex-col gap-3">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/30" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t('insights.searchPlaceholder')}
                className="input-field pl-9"
              />
            </div>
            <div className="flex flex-wrap items-center gap-1 rounded-2xl border border-white/10 bg-black/20 p-1">
              {CATEGORY_TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setCategory(tab.id)}
                  className={`rounded-xl px-3 py-1.5 text-xs font-medium transition-all duration-200 ${
                    category === tab.id
                      ? 'bg-white/15 text-white'
                      : 'text-white/55 hover:bg-white/5 hover:text-white/80'
                  }`}
                >
                  {t(tab.labelKey)}
                </button>
              ))}
            </div>
          </div>
        )}

        {loading && (
          <ul className="mx-auto max-w-3xl space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <li key={i} className="surface-card p-4">
                <div className="space-y-2">
                  <div className="skeleton h-4 w-1/2" />
                  <div className="skeleton h-3 w-3/4" />
                  <div className="skeleton h-3 w-1/4" />
                </div>
              </li>
            ))}
          </ul>
        )}

        {!loading && items.length === 0 && (
          <EmptyState
            icon={Lightbulb}
            title={t('insights.empty.title')}
            description={t('insights.empty.description')}
          />
        )}

        {!loading && items.length > 0 && visible.length === 0 && (
          <div className="flex flex-col items-center justify-center pt-16 text-center text-white/55">
            <Search className="mb-3 h-10 w-10 opacity-40" />
            <p className="text-sm">{t('insights.noMatch')}</p>
          </div>
        )}

        {!loading && visible.length > 0 && (
          <ul className="mx-auto max-w-3xl space-y-2">{visible.map(renderRow)}</ul>
        )}
      </div>
    </div>
  )
}
