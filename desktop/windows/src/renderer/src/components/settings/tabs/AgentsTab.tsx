// Settings → Agents: connect the coding agents Omi can delegate tasks to.
// Claude Code ships built in; OpenClaw, Hermes, and Codex are external CLIs.
// We make those three easy: PATH auto-detection shows whether each CLI is
// installed, a one-click "Connect" fills + saves the known launch command and
// runs the real ACP handshake, install commands are one copy away, and Codex
// gets a paste-your-OpenAI-key lane (validated) so it needs no browser sign-in.
// The raw launch command lives under "Advanced" for power users. "Test" (and
// "Connect") spawn the agent and complete a real ACP handshake, so a green
// check means the command actually works — not just that a string was saved.

import { useEffect, useState } from 'react'
import { Bot, Terminal } from 'lucide-react'
import { SettingRow } from '../SettingRow'
import { getPreferences, setPreferences } from '../../../lib/preferences'
import { useCodingAgents } from '../../../hooks/useCodingAgents'
import { CLAUDE_SIGN_IN_FAILED } from '../../../lib/claudeSignIn'
import { useTranslation } from '../../../i18n'
import type {
  AgentDetectionMap,
  CodingAgentAuthStatus,
  CodingAgentId
} from '../../../../../shared/types'

type ExternalAgentId = Exclude<CodingAgentId, 'acp'>

type AgentGuide = {
  installCommands: string[]
  installNote?: string
  suggestedCommand: string
  docsUrl: string
}

const EXTERNAL_AGENT_GUIDES: Record<ExternalAgentId, AgentGuide> = {
  openclaw: {
    installCommands: ['npm install -g openclaw@latest'],
    suggestedCommand: 'openclaw acp',
    docsUrl: 'https://docs.openclaw.ai/install'
  },
  hermes: {
    installCommands: [],
    installNote: 'hermesInstallNote',
    suggestedCommand: 'hermes acp',
    docsUrl: 'https://hermes-agent.nousresearch.com/docs'
  },
  codex: {
    installCommands: ['npm install -g @openai/codex'],
    suggestedCommand: 'npx -y @agentclientprotocol/codex-acp',
    docsUrl: 'https://github.com/agentclientprotocol/codex-acp'
  }
}

type TestState = { running: boolean; verdict?: 'ok' | 'failed'; detail?: string }

type ClaudeAuthUi = { status: CodingAgentAuthStatus | null; busy: boolean; error?: string }

type CodexKeyUi = {
  hasKey: boolean
  input: string
  saving: boolean
  result?: { ok: boolean; msg: string }
}

export function AgentsTab(): React.JSX.Element {
  const { agents, refresh } = useCodingAgents()
  const { t } = useTranslation()
  const [commands, setCommands] = useState<Partial<Record<ExternalAgentId, string>>>(
    () => getPreferences().agentCommands ?? {}
  )
  const [tests, setTests] = useState<Partial<Record<CodingAgentId, TestState>>>({})
  const [claudeAuth, setClaudeAuth] = useState<ClaudeAuthUi>({ status: null, busy: false })
  const [detection, setDetection] = useState<Partial<AgentDetectionMap>>({})
  const [advancedOpen, setAdvancedOpen] = useState<Partial<Record<ExternalAgentId, boolean>>>({})
  const [copied, setCopied] = useState<Partial<Record<ExternalAgentId, boolean>>>({})
  const [codexKey, setCodexKey] = useState<CodexKeyUi>({ hasKey: false, input: '', saving: false })

  const refreshClaudeAuth = (): void => {
    void window.omi
      .codingAgentAuthStatus()
      .then((status) => setClaudeAuth((a) => ({ ...a, status })))
      .catch(() => {})
  }

  const refreshDetection = (): void => {
    void window.omi
      .codingAgentDetect()
      .then(setDetection)
      .catch(() => {})
  }

  const refreshCodexKey = (): void => {
    void window.omi
      .codingAgentCodexKeyStatus()
      .then((s) => setCodexKey((k) => ({ ...k, hasKey: s.hasKey })))
      .catch(() => {})
  }

  // Load the Claude Code sign-in state on mount, and re-check whenever a
  // delegated task reports it needs auth (so the row flips to "Sign in" the
  // moment the user's token is rejected mid-task). Also PATH-detect the external
  // CLIs and load the Codex key status once.
  useEffect(() => {
    refreshClaudeAuth()
    refreshDetection()
    refreshCodexKey()
    return window.omi.onCodingAgentEvent((event) => {
      if (event.type === 'auth_required' && event.adapterId === 'acp') refreshClaudeAuth()
    })
  }, [])

  const signInToClaude = (): void => {
    setClaudeAuth((a) => ({ ...a, busy: true, error: undefined }))
    setTests((t) => ({ ...t, acp: { running: false } }))
    // Connecting the coding agent is a plain OAuth (Mac parity) — launch the
    // Claude Code browser sign-in directly, with NO upsell sheet. The
    // "Upgrade to Omi Pro" ClaudeAuthSheet is reserved for the mid-turn
    // auth_required event (see claudeSignIn.ts), so a Pro user connecting here
    // is never paywalled. Reflect the resulting status / surface a failure.
    void window.omi
      .codingAgentStartAuth()
      .then((r) =>
        setClaudeAuth({ status: r.status, busy: false, error: r.ok ? undefined : r.error })
      )
      .catch(() =>
        setClaudeAuth({
          status: { connected: false, expiresAt: null },
          busy: false,
          error: CLAUDE_SIGN_IN_FAILED
        })
      )
  }

  const signOutOfClaude = (): void => {
    void window.omi
      .codingAgentSignOut()
      .then((status) => {
        setClaudeAuth({ status, busy: false })
        setTests((t) => ({ ...t, acp: { running: false } }))
      })
      .catch(() => {})
  }

  const saveCommand = (id: ExternalAgentId): void => {
    const trimmed = commands[id]?.trim()
    const next = { ...(getPreferences().agentCommands ?? {}) }
    if (trimmed) next[id] = trimmed
    else delete next[id]
    setPreferences({ agentCommands: next })
    setTests((t) => ({ ...t, [id]: {} }))
    refresh()
  }

  const runTest = (id: CodingAgentId): void => {
    setTests((t) => ({ ...t, [id]: { running: true } }))
    void window.omi
      .codingAgentTest(id, getPreferences().agentCommands)
      .then((r) => {
        // A needs-auth verdict for Claude Code means the token is gone/expired —
        // reflect it in the sign-in row rather than as a bare test failure.
        if (r.needsAuth) refreshClaudeAuth()
        setTests((t) => ({
          ...t,
          [id]: { running: false, verdict: r.ok ? 'ok' : 'failed', detail: r.error }
        }))
      })
      .catch((e: Error) =>
        setTests((t) => ({ ...t, [id]: { running: false, verdict: 'failed', detail: e.message } }))
      )
  }

  // One-click Connect: fill + save the known launch command, then run the real
  // handshake. The row flips to "connected" as soon as the command is saved; the
  // Test line then confirms the agent actually answered.
  const connect = (id: ExternalAgentId): void => {
    const cmd = EXTERNAL_AGENT_GUIDES[id].suggestedCommand
    const next = { ...(getPreferences().agentCommands ?? {}), [id]: cmd }
    setCommands((c) => ({ ...c, [id]: cmd }))
    setPreferences({ agentCommands: next })
    refresh()
    runTest(id)
  }

  const disconnect = (id: ExternalAgentId): void => {
    const next = { ...(getPreferences().agentCommands ?? {}) }
    delete next[id]
    setCommands((c) => {
      const n = { ...c }
      delete n[id]
      return n
    })
    setPreferences({ agentCommands: next })
    setTests((t) => ({ ...t, [id]: {} }))
    refresh()
  }

  const copyInstall = (id: ExternalAgentId): void => {
    const cmds = EXTERNAL_AGENT_GUIDES[id].installCommands
    if (cmds.length === 0) return
    void navigator.clipboard
      .writeText(cmds.join('\n'))
      .then(() => {
        setCopied((s) => ({ ...s, [id]: true }))
        setTimeout(() => setCopied((s) => ({ ...s, [id]: false })), 1500)
      })
      .catch(() => {})
  }

  const saveCodexKey = (): void => {
    const key = codexKey.input.trim()
    if (!key) return
    setCodexKey((k) => ({ ...k, saving: true, result: undefined }))
    void window.omi
      .codingAgentSetCodexKey(key)
      .then((r) => {
        setCodexKey({
          hasKey: r.hasKey,
          input: '',
          saving: false,
          result: r.ok
            ? { ok: true, msg: r.warning ?? t('settings.agents.keySavedVerified') }
            : { ok: false, msg: r.error ?? t('settings.agents.keySaveFailed') }
        })
      })
      .catch(() =>
        setCodexKey((k) => ({
          ...k,
          saving: false,
          result: { ok: false, msg: t('settings.agents.keySaveFailed') }
        }))
      )
  }

  const removeCodexKey = (): void => {
    setCodexKey((k) => ({ ...k, saving: true, result: undefined }))
    void window.omi
      .codingAgentSetCodexKey('')
      .then((r) =>
        setCodexKey({
          hasKey: r.hasKey,
          input: '',
          saving: false,
          result: { ok: true, msg: t('settings.agents.keyRemoved') }
        })
      )
      .catch(() => setCodexKey((k) => ({ ...k, saving: false })))
  }

  const testLine = (id: CodingAgentId): React.JSX.Element | null => {
    const state = tests[id]
    if (!state?.verdict) return null
    return state.verdict === 'ok' ? (
      <div className="mt-2 text-sm text-emerald-400">{t('settings.agents.connectedHandshake')}</div>
    ) : (
      <div className="mt-2 text-sm text-amber-400">
        {state.detail ?? t('settings.agents.failedHandshake')}
      </div>
    )
  }

  const claudeConnected = claudeAuth.status?.connected ?? false

  const renderExternalAgent = (id: ExternalAgentId): React.JSX.Element => {
    const guide = EXTERNAL_AGENT_GUIDES[id]
    const info = agents.find((a) => a.id === id)
    const displayName = info?.displayName ?? id
    const connected = info?.connected ?? false
    const det = detection[id]
    const installed = det?.installed ?? false
    const busy = tests[id]?.running ?? false
    const descriptionKey =
      id === 'openclaw'
        ? 'settings.agents.openclawDescription'
        : id === 'hermes'
          ? 'settings.agents.hermesDescription'
          : 'settings.agents.codexDescription'
    const authNoteKey =
      id === 'openclaw'
        ? 'settings.agents.openclawAuthNote'
        : id === 'hermes'
          ? 'settings.agents.hermesAuthNote'
          : 'settings.agents.codexAuthNote'

    return (
      <SettingRow
        key={id}
        icon={Terminal}
        title={displayName}
        subtitle={t(descriptionKey)}
        keywords={`${id} coding agent acp command connect install detect api key`}
        dot={connected ? 'on' : 'off'}
        note={
          det ? (
            installed ? (
              <span className="text-sm text-emerald-400">
                {det.version
                  ? t('settings.agents.cliInstalledWithVersion', { version: det.version })
                  : t('settings.agents.cliInstalled')}
              </span>
            ) : (
              <span className="text-sm text-text-tertiary">{t('settings.agents.cliNotFound')}</span>
            )
          ) : null
        }
        control={
          connected ? (
            <div className="flex items-center gap-2">
              <button
                onClick={() => runTest(id)}
                disabled={busy}
                className="btn-ghost disabled:opacity-40"
              >
                {busy ? t('settings.agents.testing') : t('settings.agents.test')}
              </button>
              <button onClick={() => disconnect(id)} className="btn-ghost">
                {t('settings.agents.disconnect')}
              </button>
            </div>
          ) : (
            <button
              onClick={() => connect(id)}
              disabled={busy}
              className="btn-ghost disabled:opacity-40"
            >
              {busy ? t('settings.agents.connecting') : t('settings.agents.connect')}
            </button>
          )
        }
      >
        {/* Install guidance when the CLI isn't detected. */}
        {!installed && (
          <div className="mb-3 rounded-lg bg-white/[0.04] p-3 text-sm text-text-tertiary">
            <div className="mb-1 font-medium text-text-secondary">
              {t('settings.agents.installTitle', { name: displayName })}
            </div>
            {guide.installCommands.map((cmd) => (
              <code key={cmd} className="mb-1 block font-mono text-xs text-text-secondary">
                {cmd}
              </code>
            ))}
            {guide.installNote && (
              <div className="mb-1 text-xs">{t('settings.agents.hermesInstallNote')}</div>
            )}
            <div className="mt-2 flex items-center gap-4">
              {guide.installCommands.length > 0 && (
                <button onClick={() => copyInstall(id)} className="text-xs underline">
                  {copied[id] ? t('settings.agents.copied') : t('settings.agents.copyInstall')}
                </button>
              )}
              <a
                href={guide.docsUrl}
                target="_blank"
                rel="noreferrer"
                className="text-xs underline"
              >
                {t('settings.agents.setupGuide')}
              </a>
            </div>
          </div>
        )}

        {/* Sign-in pointer (we don't automate these external logins). */}
        {!connected && <div className="mb-3 text-sm text-text-tertiary">{t(authNoteKey)}</div>}

        {/* Codex-only: paste-your-OpenAI-key lane (validated, no browser sign-in). */}
        {guide.suggestedCommand.includes('codex') && (
          <div className="mb-3 rounded-lg bg-white/[0.04] p-3">
            <div className="mb-1 text-sm font-medium text-text-secondary">
              {t('settings.agents.apiKeyTitle')}
            </div>
            <div className="mb-2 text-xs text-text-tertiary">
              {codexKey.hasKey
                ? t('settings.agents.apiKeySaved')
                : t('settings.agents.apiKeyPrompt')}
            </div>
            <div className="flex items-center gap-2">
              <input
                type="password"
                value={codexKey.input}
                onChange={(e) => setCodexKey((k) => ({ ...k, input: e.target.value }))}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    saveCodexKey()
                  }
                }}
                placeholder={
                  codexKey.hasKey
                    ? t('settings.agents.apiKeyPlaceholderSaved')
                    : t('settings.agents.apiKeyPlaceholderEmpty')
                }
                className="glass-subtle w-full rounded-lg px-4 py-3 font-mono text-sm text-text-secondary focus:outline-none"
                spellCheck={false}
                autoComplete="off"
              />
              <button
                onClick={saveCodexKey}
                disabled={codexKey.saving || !codexKey.input.trim()}
                className="btn-ghost shrink-0 disabled:opacity-40"
              >
                {codexKey.saving ? t('settings.agents.saving') : t('settings.agents.save')}
              </button>
              {codexKey.hasKey && (
                <button
                  onClick={removeCodexKey}
                  disabled={codexKey.saving}
                  className="btn-ghost shrink-0 disabled:opacity-40"
                >
                  {t('settings.agents.remove')}
                </button>
              )}
            </div>
            {codexKey.result && (
              <div
                className={`mt-2 text-xs ${codexKey.result.ok ? 'text-emerald-400' : 'text-amber-400'}`}
              >
                {codexKey.result.msg}
              </div>
            )}
          </div>
        )}

        {/* Advanced: the raw launch command (original manual path, for power users). */}
        <button
          onClick={() => setAdvancedOpen((s) => ({ ...s, [id]: !s[id] }))}
          className="text-xs text-text-tertiary underline"
        >
          {advancedOpen[id] ? t('settings.agents.advancedHide') : t('settings.agents.advancedShow')}
        </button>
        {advancedOpen[id] && (
          <div className="mt-2 flex items-center gap-2">
            <input
              value={commands[id] ?? ''}
              onChange={(e) => setCommands((c) => ({ ...c, [id]: e.target.value }))}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  saveCommand(id)
                }
              }}
              placeholder={t('settings.agents.launchCommandPlaceholder', {
                command: guide.suggestedCommand
              })}
              className="glass-subtle w-full rounded-lg px-4 py-3 font-mono text-sm text-text-secondary focus:outline-none"
              spellCheck={false}
            />
            <button onClick={() => saveCommand(id)} className="btn-ghost shrink-0">
              {t('settings.agents.save')}
            </button>
          </div>
        )}
        {testLine(id)}
      </SettingRow>
    )
  }

  return (
    <div>
      <p className="mb-2 text-sm text-text-tertiary">{t('settings.agents.intro')}</p>

      <SettingRow
        icon={Bot}
        title={t('settings.agents.claudeTitle')}
        subtitle={
          claudeConnected
            ? t('settings.agents.claudeSubtitleConnected')
            : t('settings.agents.claudeSubtitleDisconnected')
        }
        keywords="claude code anthropic coding agent builtin sign in login authenticate"
        dot={claudeConnected ? 'on' : 'off'}
        control={
          claudeConnected ? (
            <div className="flex items-center gap-2">
              <button
                onClick={() => runTest('acp')}
                disabled={tests.acp?.running}
                className="btn-ghost disabled:opacity-40"
              >
                {tests.acp?.running ? t('settings.agents.testing') : t('settings.agents.test')}
              </button>
              <button onClick={signOutOfClaude} className="btn-ghost">
                {t('settings.agents.disconnect')}
              </button>
            </div>
          ) : (
            <button
              onClick={signInToClaude}
              disabled={claudeAuth.busy || claudeAuth.status === null}
              className="btn-ghost disabled:opacity-40"
            >
              {claudeAuth.busy
                ? t('settings.agents.signingIn')
                : t('settings.agents.signInToClaude')}
            </button>
          )
        }
      >
        {claudeAuth.busy && (
          <div className="mt-2 text-sm text-text-tertiary">{t('settings.agents.signInNote')}</div>
        )}
        {claudeAuth.error && <div className="mt-2 text-sm text-amber-400">{claudeAuth.error}</div>}
        {claudeConnected && testLine('acp')}
      </SettingRow>

      {(Object.keys(EXTERNAL_AGENT_GUIDES) as ExternalAgentId[]).map((id) =>
        renderExternalAgent(id)
      )}
    </div>
  )
}
