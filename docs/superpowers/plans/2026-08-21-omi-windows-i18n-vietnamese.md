# Omi Windows i18n (Vietnamese) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a full UI i18n system to the Omi Windows desktop app with a **Language** tab in Settings, offering **English** and **Tiếng Việt**, where switching language immediately re-renders the entire main-window UI in Vietnamese and persists across launches.

**Architecture:** react-i18next initialized once in a dedicated module (`src/renderer/src/i18n/index.ts`) with bundled `en.json` / `vi.json` locale resources; components use `useTranslation` re-exported from that module so tests work without manual init. The chosen UI language persists through the app's existing preferences system (`lib/preferences.ts`, localStorage-backed, new `uiLanguage` field) — never the existing `language` field (that one is the STT spoken-language).

**Tech Stack:** Electron 39 + React 19 + TypeScript + Tailwind, electron-vite, vitest (jsdom), pnpm 10 (Node 22.23.2 at `C:\Omi\.node22`), `react-i18next` + `i18next` (new deps).

**Spec:** Approved in chat (brainstorming, 2026-08-21): full-UI translation scope, Language tab in Settings, persistence, AI-generated content stays untranslated.

## Global Constraints

- Node must be 22.x (`>=22.19 <23`) — use `C:\Omi\.node22\pnpm.cmd` for every pnpm command; never system Node 24.
- The release app is installed and RUNNING on this machine; dev must run with `OMI_SANDBOX=dev1` to get its own userData + single-instance lock (see `src/main/index.ts:383-393`). Never kill the installed app's processes.
- Never touch the existing `Preferences.language` field (STT spoken language). New field: `Preferences.uiLanguage`.
- Do NOT translate: AI-generated content (transcripts, chat replies, summaries, insights, agent output), backend-provided data (app catalog names, persona names), brand name "Omi", keyboard-shortcut key names (e.g. `Ctrl+Shift+Space`), the STT language list labels in `lib/languages.ts`.
- All new UI strings go through `t('...')`. Hardcoded English literals in JSX inside the files listed below are the defect being removed.
- JSON locale files are formatted with `jq --indent 4` per repo formatting rules.
- Prettier runs on staged files via the repo pre-commit hook (installed? verify in Task 1; if absent, run `npx prettier --write` manually on changed files).
- Commit message style: conventional (`feat:`, `test:`, `chore:`).
- `C:\Omi\.node22` must never be committed (add to `.gitignore` if needed).
- Feature branch: `feat/i18n-vietnamese`, pushed to `origin` (the fork `Edeys/omi`).

---

### Task 1: Dev instance runs under OMI_SANDBOX

**Files:**
- Modify: `.gitignore` (repo root) — add `.node22/` if not covered
- No source changes.

**Interfaces:**
- Produces: a working `pnpm run dev` session on this machine that stays alive (prerequisite for every visual verification step in later tasks).

- [ ] **Step 1: Confirm installed-app collision diagnosis**

Run: `Get-Process | Where-Object { $_.ProcessName -match 'omi-windows' } | Measure-Object | Select -Expand Count`
Expected: > 0 (release app running). This is why a plain `pnpm run dev` exits silently (single-instance lock at `src/main/index.ts:392`).

- [ ] **Step 2: Ensure `.node22` is gitignored**

Check root `.gitignore`; if `C:\Omi\.node22` is not ignored, append `.node22/`. Verify: `git status --short` shows no `.node22` entries.

- [ ] **Step 3: Launch dev with sandbox**

Run (in `desktop/windows`, background, logs to `dev-out.log` / `dev-err.log`):
```powershell
$env:OMI_SANDBOX = 'dev1'
Start-Process -FilePath "C:\Omi\.node22\pnpm.cmd" -ArgumentList "run","dev" -WorkingDirectory "C:\Omi\desktop\windows" -RedirectStandardOutput "C:\Omi\desktop\windows\dev-out.log" -RedirectStandardError "C:\Omi\desktop\windows\dev-err.log" -WindowStyle Hidden
```
Wait 45s, then run:
```powershell
Get-Content dev-out.log -Tail 5
Get-Process | Where-Object { $_.ProcessName -match 'electron' } | Select ProcessName,Id,MainWindowTitle
```
Expected: `starting electron app...` and at least one `electron` process ALIVE (MainWindowTitle non-empty), and the app window visible on the user's screen. The 10-minute CDP/DevTools line alone is not success — the process must stay alive.

- [ ] **Step 4: Verify app is functional in sandbox**

The window must render the Omi UI (login or home). Confirm with the user that the window opened and shows the app. Leave the dev session RUNNING for the rest of the plan.

- [ ] **Step 5: Commit**

```bash
git add .gitignore
git commit -m "chore: ignore local .node22 toolchain dir"
```

---

### Task 2: i18n infrastructure (react-i18next + locales + persistence)

**Files:**
- Create: `src/renderer/src/i18n/index.ts`
- Create: `src/renderer/src/i18n/locales/en.json`
- Create: `src/renderer/src/i18n/locales/vi.json`
- Create: `src/renderer/src/i18n/locales.parity.test.ts`
- Modify: `src/renderer/src/main.tsx` (add i18n import + init before `createRoot`)
- Modify: `src/renderer/src/lib/preferences.ts` (add `uiLanguage?: string` to `Preferences`)
- Modify: `package.json` + `pnpm-lock.yaml` (new deps)

**Interfaces:**
- Consumes: `getPreferences` / `setPreferences` / `onPreferencesChange` from `src/renderer/src/lib/preferences.ts`.
- Produces: module `src/renderer/src/i18n` exporting `i18n` (initialized i18next instance, default `en`, `fallbackLng: 'en'`, `lng` read from `getPreferences().uiLanguage ?? 'en'`), `useTranslation` (react-i18next hook bound to that instance), `changeUiLanguage(code: string): void` (persists via `setPreferences({ uiLanguage: code })` then `void i18n.changeLanguage(code)`).
- Locale key structure: nested JSON grouped by surface, e.g. `settings.tabs.general`, `settings.language.title`, `home.title`. `en.json` and `vi.json` MUST have identical key sets.

- [ ] **Step 1: Add dependencies**

```powershell
C:\Omi\.node22\pnpm.cmd add i18next react-i18next
```
Expected: packages added to `dependencies`, `pnpm-lock.yaml` updated.

- [ ] **Step 2: Add `uiLanguage` to Preferences**

In `src/renderer/src/lib/preferences.ts`, add to the `Preferences` type (near the existing `language` field):
```ts
  // UI display language (i18n), e.g. 'en' | 'vi'. Separate from `language`
  // (STT spoken language). Undefined -> 'en'.
  uiLanguage?: string
```
Also add a normalizer next to `normalizeFontScale` so a junk value falls back to `en`:
```ts
function normalizeUiLanguage(p: Preferences): void {
  if (p.uiLanguage !== undefined && typeof p.uiLanguage !== 'string') {
    delete p.uiLanguage
  }
}
```
Call it in `load()` alongside the existing normalizer (read the file's `load()` to place it correctly).

- [ ] **Step 3: Write the parity test (fails first)**

Create `src/renderer/src/i18n/locales.parity.test.ts`:
```ts
import { describe, expect, it } from 'vitest'
import en from './locales/en.json'
import vi from './locales/vi.json'

function flattenKeys(obj: Record<string, unknown>, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    typeof v === 'object' && v !== null
      ? flattenKeys(v as Record<string, unknown>, `${prefix}${k}.`)
      : [`${prefix}${k}`]
  )
}

describe('locale parity', () => {
  it('en.json and vi.json have identical key sets', () => {
    const enKeys = flattenKeys(en).sort()
    const viKeys = flattenKeys(vi).sort()
    expect(viKeys).toEqual(enKeys)
  })

  it('every vi value is non-empty and not a copy of the en key path', () => {
    const check = (enObj: Record<string, unknown>, viObj: Record<string, unknown>, prefix: string): void => {
      for (const k of Object.keys(enObj)) {
        const enV = enObj[k]
        const viV = viObj[k]
        if (typeof enV === 'object' && enV !== null) {
          check(enV as Record<string, unknown>, viV as Record<string, unknown>, `${prefix}${k}.`)
        } else {
          expect(String(viV).trim().length, `${prefix}${k}`).toBeGreaterThan(0)
          expect(String(viV), `${prefix}${k}`).not.toBe(String(enV))
        }
      }
    }
    check(en, vi, '')
  })
})
```

- [ ] **Step 4: Create the locale files (minimal, English only values for now)**

`en.json` — a few starter keys (this file grows in Tasks 3–6; keep this step's JSON small so the parity test has something to check):
```json
{
    "app": {
        "name": "Omi"
    },
    "settings": {
        "title": "Settings",
        "back": "Back",
        "searchPlaceholder": "Search settings…",
        "tabs": {
            "general": "General",
            "memories": "Memories",
            "agents": "Agents",
            "transcription": "Transcription",
            "rewind": "Rewind",
            "notifications": "Notifications",
            "privacy": "Privacy",
            "account": "Account",
            "planUsage": "Plan & Usage",
            "shortcuts": "Shortcuts",
            "advanced": "Advanced",
            "about": "About",
            "language": "Language"
        },
        "language": {
            "title": "Language",
            "subtitle": "Choose the language for the app interface. Content generated by AI keeps its own language."
        }
    },
    "common": {
        "english": "English",
        "vietnamese": "Tiếng Việt"
    }
}
```

`vi.json` — same keys, Vietnamese values:
```json
{
    "app": {
        "name": "Omi"
    },
    "settings": {
        "title": "Cài đặt",
        "back": "Quay lại",
        "searchPlaceholder": "Tìm kiếm cài đặt…",
        "tabs": {
            "general": "Chung",
            "memories": "Ký ức",
            "agents": "Trợ lý",
            "transcription": "Phiên âm",
            "rewind": "Quay lại",
            "notifications": "Thông báo",
            "privacy": "Quyền riêng tư",
            "account": "Tài khoản",
            "planUsage": "Gói & Hạn mức",
            "shortcuts": "Phím tắt",
            "advanced": "Nâng cao",
            "about": "Giới thiệu",
            "language": "Ngôn ngữ"
        },
        "language": {
            "title": "Ngôn ngữ",
            "subtitle": "Chọn ngôn ngữ hiển thị của giao diện. Nội dung do AI tạo ra vẫn giữ nguyên ngôn ngữ của nó."
        }
    },
    "common": {
        "english": "English",
        "vietnamese": "Tiếng Việt"
    }
}
```

- [ ] **Step 5: Create the i18n module**

`src/renderer/src/i18n/index.ts`:
```ts
import i18n from 'i18next'
import { initReactI18next, useTranslation as useReactI18next } from 'react-i18next'
import en from './locales/en.json'
import vi from './locales/vi.json'
import { getPreferences, setPreferences } from '../lib/preferences'

export const UI_LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'vi', label: 'Tiếng Việt' }
] as const

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    vi: { translation: vi }
  },
  lng: getPreferences().uiLanguage ?? 'en',
  fallbackLng: 'en',
  interpolation: { escapeValue: false }
})

export { i18n }
export const useTranslation = useReactI18next

export function changeUiLanguage(code: string): void {
  setPreferences({ uiLanguage: code })
  void i18n.changeLanguage(code)
}
```

- [ ] **Step 6: Wire into the renderer entry**

In `src/renderer/src/main.tsx`, before the font imports or right after them (any point before `createRoot`):
```ts
import './i18n'
```
(i18n module initializes at import time; `createRoot` renders after, so the first paint already uses the persisted language.)

- [ ] **Step 7: Run the parity test (must fail — vi.json values match? no: Step 4 already wrote real vi values, so it passes; the fail-first test is the key-set invariant, verify it catches a real defect: temporarily delete one vi key, run, expect FAIL, restore)**

Run: `C:\Omi\.node22\pnpm.cmd exec vitest run src/renderer/src/i18n/locales.parity.test.ts`
Expected: PASS (and the manual mutation check above proves it fails when a key is missing).

- [ ] **Step 8: Typecheck + lint + full test**

Run: `C:\Omi\.node22\pnpm.cmd run typecheck` then `C:\Omi\.node22\pnpm.cmd run lint` then `C:\Omi\.node22\pnpm.cmd test`
Expected: all green (lint may warn on existing pre-existing issues only; no NEW ones from this task).

- [ ] **Step 9: Commit**

```bash
git add package.json pnpm-lock.yaml src/renderer/src/i18n src/renderer/src/main.tsx src/renderer/src/lib/preferences.ts
git commit -m "feat: add i18n infrastructure with en/vi locales"
```

---

### Task 3: Language tab in Settings

**Files:**
- Modify: `src/renderer/src/components/settings/tabs.ts` (add `language` tab id + entry)
- Create: `src/renderer/src/components/settings/tabs/LanguageTab.tsx`
- Modify: `src/renderer/src/pages/Settings.tsx` (register `LanguageTab` in `TAB_COMPONENTS`)
- Create: `src/renderer/src/components/settings/tabs/LanguageTab.test.tsx`

**Interfaces:**
- Consumes: `changeUiLanguage`, `useTranslation`, `UI_LANGUAGES` from `../../i18n`; `SettingRow` from `../SettingRow`.
- Produces: settings tab id `'language'` visible in the rail; switching the dropdown re-renders the UI in the chosen language immediately and persists.

- [ ] **Step 1: Write the failing test**

`src/renderer/src/components/settings/tabs/LanguageTab.test.tsx`:
```tsx
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { LanguageTab } from './LanguageTab'
import { changeUiLanguage } from '../../../i18n'
import { getPreferences } from '../../../lib/preferences'

vi.mock('../../../i18n', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../i18n')>()
  return { ...actual, changeUiLanguage: vi.fn() }
})

describe('LanguageTab', () => {
  it('renders a language selector with English and Vietnamese options', () => {
    render(<LanguageTab />)
    expect(screen.getByRole('combobox')).toBeTruthy()
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['English', 'Tiếng Việt'])
  })

  it('switching to Vietnamese calls changeUiLanguage with "vi"', async () => {
    const user = userEvent.setup()
    render(<LanguageTab />)
    await user.selectOptions(screen.getByRole('combobox'), 'vi')
    expect(changeUiLanguage).toHaveBeenCalledWith('vi')
  })

  it('shows the persisted language as the current selection', () => {
    expect(getPreferences().uiLanguage ?? 'en').toBe('en')
  })
})
```
(If `@testing-library/user-event` is not installed, use `fireEvent.change` instead — check `devDependencies` first.)

- [ ] **Step 2: Run it — expect FAIL (LanguageTab doesn't exist yet)**

Run: `C:\Omi\.node22\pnpm.cmd exec vitest run src/renderer/src/components/settings/tabs/LanguageTab.test.tsx`
Expected: FAIL (module not found).

- [ ] **Step 3: Add the tab id**

In `src/renderer/src/components/settings/tabs.ts`:
- Add `'language'` to the `SettingsTabId` union (after `'general'`).
- Add to `SETTINGS_TABS` (import `Languages` from `lucide-react`):
```ts
  { id: 'language', label: 'Language', Icon: Languages },
```
Note: the rail currently renders `label` directly — Task 4 switches it to `t()`; keep `label` as-is for now (it is also used by search `keywords`).

- [ ] **Step 4: Create LanguageTab**

`src/renderer/src/components/settings/tabs/LanguageTab.tsx`:
```tsx
import { Languages } from 'lucide-react'
import { useTranslation, UI_LANGUAGES, changeUiLanguage } from '../../../i18n'
import { SettingRow } from '../SettingRow'

export function LanguageTab(): React.JSX.Element {
  const { t, i18n } = useTranslation()
  const current = i18n.language?.startsWith('vi') ? 'vi' : 'en'
  return (
    <SettingRow
      icon={Languages}
      title={t('settings.language.title')}
      subtitle={t('settings.language.subtitle')}
      keywords="language ngon ngu tieng viet english"
      control={
        <select
          value={current}
          onChange={(e) => changeUiLanguage(e.target.value)}
          className="rounded-md bg-white/10 px-2 py-1.5 text-sm text-white focus:outline-none"
        >
          {UI_LANGUAGES.map((l) => (
            <option key={l.code} value={l.code} className="bg-neutral-900">
              {l.label}
            </option>
          ))}
        </select>
      }
    />
  )
}
```

- [ ] **Step 5: Register in Settings.tsx**

In `src/renderer/src/pages/Settings.tsx`: import `LanguageTab` and add to `TAB_COMPONENTS`:
```ts
  language: LanguageTab,
```

- [ ] **Step 6: Run the test — expect PASS**

Run: `C:\Omi\.node22\pnpm.cmd exec vitest run src/renderer/src/components/settings/tabs/LanguageTab.test.tsx`
Expected: PASS.

- [ ] **Step 7: Typecheck + lint + affected settings tests**

Run: `C:\Omi\.node22\pnpm.cmd run typecheck` and `C:\Omi\.node22\pnpm.cmd exec vitest run src/renderer/src/components/settings src/renderer/src/pages/Settings.backNav.test.tsx`
Expected: all green.

- [ ] **Step 8: Visual check in the running dev session**

The dev session (Task 1) is still running with HMR. In the app: open Settings → the new "Language" tab appears in the rail; selecting "Tiếng Việt" switches the Settings title ("Settings" → "Cài đặt"), tab labels, and Back button immediately (those three are already `t()`-wired from Task 2's keys via Task 4 — if not yet, they flip after Task 4; minimum here: the tab exists and the dropdown switches `i18n.language`, visible via the parity of any already-translated string). Confirm with the user visually.

- [ ] **Step 9: Commit**

```bash
git add src/renderer/src/components/settings/tabs.ts src/renderer/src/components/settings/tabs/LanguageTab.tsx src/renderer/src/components/settings/tabs/LanguageTab.test.tsx src/renderer/src/pages/Settings.tsx
git commit -m "feat: add Language tab to Settings"
```

---

### Task 4: Translate the Settings surface

**Files (all under `src/renderer/src/components/settings/`):**
- Modify: `SettingsTabRail.tsx` (Back, Settings title, Search placeholder, tab labels via `t`)
- Modify: `SettingsTabPanel.tsx` (panel headers if any — read the file first)
- Modify: `SettingRow.tsx` (component's own chrome if any)
- Modify: `tabs/GeneralTab.tsx`, `tabs/AgentsTab.tsx`, `tabs/TranscriptionTab.tsx`, `tabs/RewindTab.tsx`, `tabs/NotificationsTab.tsx`, `tabs/PrivacyTab.tsx`, `tabs/AccountTab.tsx`, `tabs/PlanUsageTab.tsx`, `tabs/ShortcutsTab.tsx`, `tabs/AdvancedTab.tsx`, `tabs/AboutTab.tsx`
- Modify: `src/renderer/src/i18n/locales/en.json` + `vi.json` (all new keys)
- Modify: any small shared components used only by settings tabs (e.g. `FontSizeCard.tsx`, `Toggle.tsx` chrome text, `SettingRow` titles/subtitles live in the tabs themselves)

**Interfaces:**
- Consumes: `useTranslation` from `../../i18n` (path from `components/settings/tabs/*` is `../../../i18n`).
- Produces: every user-visible string in the Settings surface routed through `t()`; `vi.json` contains complete Vietnamese translations for it.

- [ ] **Step 1: Establish the extraction pattern on SettingsTabRail**

Before:
```tsx
<ArrowLeft className="h-4 w-4" strokeWidth={1.75} />
Back
```
After:
```tsx
const { t } = useTranslation()
// ...
<ArrowLeft className="h-4 w-4" strokeWidth={1.75} />
{t('settings.back')}
```
Do the same for `Settings` title → `t('settings.title')` and `Search settings…` placeholder → `t('settings.searchPlaceholder')`. Tab labels: change the rail map to `{SETTINGS_TABS.map(({ id, label, Icon }) => { ... {t(\`settings.tabs.${id}\`)} ... })` — since `SettingsTabId` values ('plan-usage') must map to camelCase keys, translate id→key: replace `-` + lowercase with uppercase (`plan-usage` → `planUsage`); the existing `label` stays for search keywords. (Or simpler: keep per-tab `t` calls with a small `TAB_KEYS` map; choose one, be consistent.)

- [ ] **Step 2: Extract GeneralTab fully (the pattern-setting example)**

Work through every `SettingRow` in `GeneralTab.tsx` (ScreenCaptureRow, AudioRecordingRow, ActionAutomationRow, ScreenAnalysisRow, Chat history, MultiChatRow, LegacyHomeRow, MeetingDetectionRow, LaunchAtLoginRow, FontSizeCard). For each `title`/`subtitle`/option text add a key under `settings.general.*` in both JSON files with real translations. Example (Chat history row):
- key: `settings.general.chatHistoryTitle` → en `"Chat history"` / vi `"Lịch sử trò chuyện"`
- key: `settings.general.chatHistorySubtitle` → en `"By default, one ongoing conversation (shared with the floating bar) that persists across launches — scroll up in chat to load older messages. Or start a fresh conversation each launch."` / vi: full Vietnamese translation (write the natural translation, e.g. `"Mặc định, một cuộc trò chuyện liên tục (dùng chung với thanh nổi) được giữ qua các lần mở ứng dụng — cuộn lên trong khung chat để xem tin nhắn cũ hơn. Hoặc bắt đầu cuộc trò chuyện mới mỗi lần khởi động."`)
- option text: `settings.general.chatHistoryInfinite` → en `"One ongoing conversation (default)"` / vi `"Một cuộc trò chuyện liên tục (mặc định)"`; `settings.general.chatHistoryPerLaunch` → en `"New conversation each launch"` / vi `"Cuộc trò chuyện mới mỗi lần khởi động"`

Then replace the JSX literals with `t('settings.general.chatHistoryTitle')` etc. Keep `keywords` props in English (they feed search — search stays English-capable).

- [ ] **Step 3: Translate the remaining settings tabs**

Apply the identical pattern (extract → key → en+vi → `t()` → keep keywords) to each file in the Files list. Conventions:
- Row titles: `settings.<tabId>.<rowId>Title`; subtitles: `...Subtitle`; option/select/button texts: descriptive suffix (`...OptionInfinite`, `...ResetButton`).
- Do not translate brand "Omi", key names like `Ctrl+Shift+Space`, URLs, or AI-generated strings.
- Numbers/plurals: keep English plural logic simple; Vietnamese does not pluralize — when a string has `{count}`, use the same interpolation key in both files with a Vietnamese-appropriate template (e.g. en `"{count} items"` / vi `"{count} mục"`).

- [ ] **Step 4: Run the parity test**

Run: `C:\Omi\.node22\pnpm.cmd exec vitest run src/renderer/src/i18n/locales.parity.test.ts`
Expected: PASS (this task is where the test earns its keep).

- [ ] **Step 5: Typecheck + lint + settings tests**

Run: `C:\Omi\.node22\pnpm.cmd run typecheck`, `C:\Omi\.node22\pnpm.cmd run lint`, `C:\Omi\.node22\pnpm.cmd exec vitest run src/renderer/src/components/settings src/renderer/src/pages/Settings.backNav.test.tsx`
Expected: all green.

- [ ] **Step 6: Visual verification in the live dev session**

Switch to Tiếng Việt in Settings → Language; walk every Settings tab; confirm each renders Vietnamese and nothing breaks layout (long Vietnamese strings must not overflow — check the longest subtitle). Fix any overflow by shortening the vi translation, not by changing layout. Switch back to English; confirm full restore. Ask the user to confirm visually.

- [ ] **Step 7: Commit**

```bash
git add src/renderer/src/components/settings src/renderer/src/i18n/locales
git commit -m "feat: translate Settings surface to Vietnamese (i18n)"
```

---

### Task 5: Translate the main pages

**Files (all under `src/renderer/src/pages/`):**
- Modify: `Home.tsx`, `Memories.tsx`, `Tasks.tsx`, `Insights.tsx`, `Goals.tsx`, `Conversations.tsx`
- Modify: `src/renderer/src/i18n/locales/en.json` + `vi.json`
- Modify: the shared components those pages render that own visible chrome (whichever of `src/renderer/src/components/home/**`, `components/memories/**`, `components/tasks/**`, `components/insights/**`, `components/conversations/**`, `components/chat/**`, `components/chrome/**` the executor finds holding user-visible literals while translating each page — read each page first, then its components; do not translate data-driven components: `components/apps/**`, `components/knowledgeGraph/**` visual layer, `components/orb/**`)

**Interfaces:**
- Consumes: `useTranslation` from `../i18n`.
- Produces: Home/Memories/Tasks/Insights/Goals/Conversations + their chrome fully translated; locale keys under `home.*`, `memories.*`, `tasks.*`, `insights.*`, `goals.*`, `conversations.*`.

- [ ] **Step 1: Translate Home page + its chrome components**

Read `Home.tsx` and the components it mounts; extract every user-visible literal (headings, buttons, empty states, stat labels, chat panel headers, search placeholder, date labels like "Today"/"Yesterday" — use key `home.*`). Write en+vi values; replace with `t()`.

- [ ] **Step 2: Translate Memories, Tasks, Insights, Goals, Conversations**

Same mechanical pattern per page, keys grouped `memories.*`, `tasks.*`, `insights.*`, `goals.*`, `conversations.*`. Keep `keywords` props in English.

- [ ] **Step 3: Run the parity test + typecheck + lint**

Run: `C:\Omi\.node22\pnpm.cmd exec vitest run src/renderer/src/i18n/locales.parity.test.ts`, `C:\Omi\.node22\pnpm.cmd run typecheck`, `C:\Omi\.node22\pnpm.cmd run lint`
Expected: all green.

- [ ] **Step 4: Run the page test suites**

Run: `C:\Omi\.node22\pnpm.cmd exec vitest run src/renderer/src/pages/Home.test.tsx src/renderer/src/pages/Memories src/renderer/src/pages/Tasks.test.tsx src/renderer/src/pages/Insights.test.tsx src/renderer/src/pages/Goals.test.tsx`
Expected: all green (fix any test that asserted on English literals by updating the assertion to the translated key's value, or by mocking — prefer updating assertions to match the en locale's rendered value).

- [ ] **Step 5: Hardcoded-literal sweep**

Run a sweep to find remaining JSX text literals in the translated files:
```powershell
rg -n '>[A-Za-z][A-Za-z ]+<' src/renderer/src/pages src/renderer/src/components/home src/renderer/src/components/chat src/renderer/src/components/chrome
```
Review each hit; translate or consciously exclude (brand, AI content, data).

- [ ] **Step 6: Visual verification in the live dev session**

Navigate every main page in Tiếng Việt and in English; confirm translations render, layout holds, and the chat panel (where user messages are typed) works. Ask the user to confirm.

- [ ] **Step 7: Commit**

```bash
git add src/renderer/src/pages src/renderer/src/components/home src/renderer/src/components/chat src/renderer/src/components/chrome src/renderer/src/i18n/locales
git commit -m "feat: translate main pages to Vietnamese (i18n)"
```

---

### Task 6: Translate remaining pages and shared chrome

**Files (all under `src/renderer/src/pages/` unless noted):**
- Modify: `Login.tsx`, `Onboarding.tsx`, `Rewind.tsx`, `KnowledgeGraph.tsx`, `ConversationDetail.tsx`, `LiveConversation.tsx`, `LegacyHome.tsx`
- Modify: `src/renderer/src/components/**` leftovers found by the sweep (bar/capture labels, glow, insight toast, dialogs, toasts, empty states) — executor judgment, enumerated in the sweep output
- Modify: `src/renderer/src/i18n/locales/en.json` + `vi.json`

**Interfaces:**
- Consumes: `useTranslation` from `../i18n`.
- Produces: complete main-window coverage — the ONLY remaining English UI is: AI-generated content, backend data, brand names, keyboard key names.

- [ ] **Step 1: Translate Login + Onboarding** (keys `login.*`, `onboarding.*`) — these must be perfect: they are the first thing a user sees.

- [ ] **Step 2: Translate Rewind, KnowledgeGraph, ConversationDetail, LiveConversation, LegacyHome** (keys `rewind.*`, `knowledgeGraph.*`, `conversationDetail.*`, `liveConversation.*`, `home.*` additions as needed).

- [ ] **Step 3: Secondary-window sweep (bar/glow/capture/insight-toast)**

Read `src/renderer/src/components/bar/**` (the always-on-top floating bar) and the `captureEntry.tsx` / `glow.tsx` / `insightToast.tsx` entries. Translate their visible labels too (keys `bar.*`, `capture.*`, `glow.*`, `insightToast.*`). They share the same bundle, so the same `useTranslation` works. If a secondary window entry needs the i18n import, add `import '../i18n'` in that entry file. Do NOT touch bar window logic — labels only (see `docs/bar-gotchas.md` — text changes are safe, window logic is not).

- [ ] **Step 4: Full locale sweep + parity test + typecheck + lint + full test suite**

Run the sweep from Task 5 Step 5 again across the whole renderer; then:
`C:\Omi\.node22\pnpm.cmd exec vitest run src/renderer/src/i18n/locales.parity.test.ts`, `C:\Omi\.node22\pnpm.cmd run typecheck`, `C:\Omi\.node22\pnpm.cmd run lint`, `C:\Omi\.node22\pnpm.cmd test`
Expected: all green.

- [ ] **Step 5: Visual verification**

In the live dev session: exercise Login/logged-out view, Rewind, Knowledge Graph, Conversation detail, and the floating bar in both languages. Ask the user to confirm.

- [ ] **Step 6: Commit**

```bash
git add src/renderer/src/pages src/renderer/src/components src/renderer/src/i18n/locales
git commit -m "feat: translate remaining pages and chrome to Vietnamese (i18n)"
```

---

### Task 7: Docs, final verification, push

**Files:**
- Modify: `desktop/windows/README.md` (document the Language feature + how to add a new language)
- No source changes unless a verification gate fails.

**Interfaces:**
- Consumes: everything from Tasks 1–6.
- Produces: a verified, documented feature branch ready on the fork.

- [ ] **Step 1: Document the feature**

Append a "## Language / Ngôn ngữ" section to `desktop/windows/README.md`: what it does (Settings → Language, English/Tiếng Việt, persisted), how to add a language (copy `en.json` shape into a new `xx.json`, register in `src/renderer/src/i18n/index.ts` resources + `UI_LANGUAGES`, parity test enforces key parity), and the constraint that AI-generated content stays untranslated.

- [ ] **Step 2: Full gate run**

Run: `C:\Omi\.node22\pnpm.cmd run typecheck` && `C:\Omi\.node22\pnpm.cmd run lint` && `C:\Omi\.node22\pnpm.cmd test`
Expected: all green. Record the results in the commit message.

- [ ] **Step 3: Fresh-instance sanity check**

Restart the dev session once (stop the background `pnpm run dev`, relaunch with `OMI_SANDBOX=dev1`), confirm: persisted language survives restart (select Tiếng Việt → restart → UI comes up Vietnamese), single-instance lock still holds against the installed app, no console errors in `dev-err.log`.

- [ ] **Step 4: Branch + commit + push**

```bash
git checkout -b feat/i18n-vietnamese
git add desktop/windows/README.md
git commit -m "docs: document Language setting and i18n extension"
git push -u origin feat/i18n-vietnamese
```
Expected: branch pushed to `https://github.com/Edeys/omi`.

- [ ] **Step 5: Report to the user**

Summarize in chat: what was built, how to run it (`OMI_SANDBOX=dev1` + `pnpm run dev` from `C:\Omi\desktop\windows`), how to build the installer (`pnpm run build:win` — note: needs MSVC Build Tools for the native rebuild step on a fresh install; the dev path used prebuilt binaries), and what remains optional (OCR/audio/automation .NET helpers).