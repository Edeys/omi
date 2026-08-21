import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { Search, X, Check, ChevronDown, SlidersHorizontal, Clock } from 'lucide-react'
import {
  MEMORY_CATEGORIES,
  type MemoryCategory,
  type MemoryLayerFilter
} from '../../lib/memoryFilters'
import { useTranslation } from '../../i18n'

// The layer filter renders Default / Short-term / Long-term only. "Archive" is a
// server-side explicit-archive scope on Mac; the default /v3/memories read never
// returns archived rows, so a client-side Archive option would always be empty —
// deferred until an archive-scoped fetch is wired. The whole control is gated on
// canonicalLifecycleExposed, so it never appears against a backend without tiers.
const LAYER_OPTIONS: readonly MemoryLayerFilter[] = ['default', 'short_term', 'long_term']

type MemoryFilterBarProps = {
  search: string
  onSearchChange: (v: string) => void
  categories: Set<MemoryCategory>
  onToggleCategory: (c: MemoryCategory) => void
  onClearCategories: () => void
  categoryCounts: Record<MemoryCategory, number>
  // Gated: only rendered when the server advertises canonical memory tiering.
  layerExposed: boolean
  layer: MemoryLayerFilter
  onLayerChange: (l: MemoryLayerFilter) => void
}

function categoryKey(c: MemoryCategory): string {
  switch (c) {
    case 'manual':
      return 'memories.filter.categoryManual'
    case 'system':
      return 'memories.filter.categorySystem'
    case 'interesting':
      return 'memories.filter.categoryInteresting'
    case 'workflow':
      return 'memories.filter.categoryWorkflow'
  }
}

function categoryButtonLabel(
  categories: Set<MemoryCategory>,
  t: (k: string, o?: Record<string, unknown>) => string
): string {
  if (categories.size === 0) return t('memories.filter.allCategories')
  if (categories.size === 1) return t(categoryKey([...categories][0]))
  return t('memories.filter.selectedCount', { count: categories.size })
}

export function MemoryFilterBar({
  search,
  onSearchChange,
  categories,
  onToggleCategory,
  onClearCategories,
  categoryCounts,
  layerExposed,
  layer,
  onLayerChange
}: MemoryFilterBarProps): React.JSX.Element {
  const { t } = useTranslation()
  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Search */}
      <div className="relative min-w-[12rem] flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/30" />
        <input
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder={t('memories.filter.searchPlaceholder')}
          className="input-field w-full py-2 pl-9 pr-9 text-sm"
        />
        {search && (
          <button
            onClick={() => onSearchChange('')}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded-md p-0.5 text-white/40 hover:text-white/80"
            aria-label={t('memories.filter.clear')}
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Category filter (multi-select) */}
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button
            type="button"
            className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-2 text-sm transition-colors ${
              categories.size > 0
                ? 'border-white/25 bg-white/10 text-white'
                : 'border-white/10 bg-black/20 text-white/70 hover:bg-white/5'
            }`}
          >
            <SlidersHorizontal className="h-3.5 w-3.5" />
            {categoryButtonLabel(categories, t)}
            <ChevronDown className="h-3.5 w-3.5 opacity-60" />
          </button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content
            align="end"
            sideOffset={8}
            className="z-[120] w-56 rounded-xl border border-white/10 bg-[var(--bg-secondary)] p-1.5 shadow-[0_16px_40px_rgba(0,0,0,0.5)]"
          >
            {MEMORY_CATEGORIES.map((c) => {
              const checked = categories.has(c)
              return (
                <DropdownMenu.CheckboxItem
                  key={c}
                  checked={checked}
                  onCheckedChange={() => onToggleCategory(c)}
                  onSelect={(e) => e.preventDefault()}
                  className="flex cursor-pointer select-none items-center gap-2 rounded-lg px-2.5 py-2 text-[13px] text-white/80 outline-none data-[highlighted]:bg-white/5"
                >
                  <span className="flex h-4 w-4 items-center justify-center rounded border border-white/25">
                    {checked && <Check className="h-3 w-3 text-white" />}
                  </span>
                  <span className="flex-1">{t(categoryKey(c))}</span>
                  <span className="text-white/35">{categoryCounts[c] ?? 0}</span>
                </DropdownMenu.CheckboxItem>
              )
            })}
            {categories.size > 0 && (
              <>
                <DropdownMenu.Separator className="my-1.5 h-px bg-white/10" />
                <DropdownMenu.Item
                  onSelect={onClearCategories}
                  className="cursor-pointer rounded-lg px-2.5 py-1.5 text-[13px] text-white/60 outline-none data-[highlighted]:bg-white/5"
                >
                  {t('memories.filter.clear')}
                </DropdownMenu.Item>
              </>
            )}
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>

      {/* Layer filter (gated on canonical tiering) */}
      {layerExposed && (
        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button
              type="button"
              className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-2 text-sm transition-colors ${
                layer !== 'default'
                  ? 'border-white/25 bg-white/10 text-white'
                  : 'border-white/10 bg-black/20 text-white/70 hover:bg-white/5'
              }`}
            >
              <Clock className="h-3.5 w-3.5" />
              {t(
                `memories.filter.${layer === 'default' ? 'layerDefault' : layer === 'short_term' ? 'layerShortTerm' : layer === 'long_term' ? 'layerLongTerm' : 'layerArchive'}`
              )}
              <ChevronDown className="h-3.5 w-3.5 opacity-60" />
            </button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              align="end"
              sideOffset={8}
              className="z-[120] w-60 rounded-xl border border-white/10 bg-[var(--bg-secondary)] p-1.5 shadow-[0_16px_40px_rgba(0,0,0,0.5)]"
            >
              <DropdownMenu.RadioGroup
                value={layer}
                onValueChange={(v) => onLayerChange(v as MemoryLayerFilter)}
              >
                {LAYER_OPTIONS.map((l) => (
                  <DropdownMenu.RadioItem
                    key={l}
                    value={l}
                    className="flex cursor-pointer select-none items-start gap-2 rounded-lg px-2.5 py-2 text-[13px] text-white/80 outline-none data-[highlighted]:bg-white/5"
                  >
                    <span className="mt-0.5 flex h-4 w-4 items-center justify-center rounded-full border border-white/25">
                      {layer === l && <span className="h-2 w-2 rounded-full bg-white" />}
                    </span>
                    <span className="flex-1">
                      <span className="block text-white/90">
                        {t(
                          `memories.filter.${l === 'default' ? 'layerDefault' : l === 'short_term' ? 'layerShortTerm' : l === 'long_term' ? 'layerLongTerm' : 'layerArchive'}`
                        )}
                      </span>
                      <span className="block text-[11px] text-white/40">
                        {t(
                          `memories.filter.${l === 'default' ? 'layerDescDefault' : l === 'short_term' ? 'layerDescShortTerm' : l === 'long_term' ? 'layerDescLongTerm' : 'layerDescArchive'}`
                        )}
                      </span>
                    </span>
                  </DropdownMenu.RadioItem>
                ))}
              </DropdownMenu.RadioGroup>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      )}
    </div>
  )
}
