import { useEffect, useState } from 'react'
import { Bell, Gauge, Focus, Brain, Sparkles, Lightbulb } from 'lucide-react'
import { SettingRow } from '../SettingRow'
import { Toggle } from '../Toggle'
import { Slider } from '../controls/Slider'
import { useTranslation } from '../../../i18n'
import type { AssistantSettingsView } from '../../../../../shared/types'

// Frequency levels 0–5, mirroring Mac's stepped slider labels and the interval
// table in main/assistants/core/notify.ts (LEVEL_INTERVALS_MS).

/**
 * Notifications tab — the opt-in that unblocks proactive assistants. Windows ships
 * with notificationFrequency=0 (Off, matching Mac's post-migration default), so
 * every proactive toast (Insight/Focus/Goals) is permanently silent until the user
 * raises the frequency here. This tab is the only surface that lets them.
 *
 * Scoped bridge only (assistantsGetSettings/SetSettings) — a whitelisted view of
 * the central app-settings store, never a generic settings pass-through. Writing a
 * setting is the whole action: the proactive coordinator re-syncs on any write.
 */
export function NotificationsTab(): React.JSX.Element {
  const [settings, setSettings] = useState<AssistantSettingsView | null>(null)
  const { t } = useTranslation()

  useEffect(() => {
    void window.omi.assistantsGetSettings().then(setSettings)
    // Stay in lock-step if the same flag is written elsewhere (tray checkbox, a
    // future backend sync) — the broadcast pushes the fresh projection.
    return window.omi.onAssistantSettingsChanged(setSettings)
  }, [])

  const patch = (p: Partial<AssistantSettingsView>): void => {
    setSettings((cur) => (cur ? { ...cur, ...p } : cur)) // optimistic
    void window.omi.assistantsSetSettings(p).then(setSettings)
  }

  const notifOn = !!settings?.notificationsEnabled
  const level = settings?.notificationFrequency ?? 0
  // Per-assistant rows read as OFF and grey out while the master toggle is off,
  // mirroring Mac's `if notificationsEnabled` reveal.
  const subDisabled = !settings || !notifOn

  const FREQUENCY_LABELS = [
    t('settings.notifications.frequencyLabelsOff'),
    t('settings.notifications.frequencyLabelsMinimal'),
    t('settings.notifications.frequencyLabelsLow'),
    t('settings.notifications.frequencyLabelsBalanced'),
    t('settings.notifications.frequencyLabelsHigh'),
    t('settings.notifications.frequencyLabelsMaximum')
  ]
  const FREQUENCY_CAPTIONS = [
    t('settings.notifications.frequencyCaptionsOff'),
    t('settings.notifications.frequencyCaptionsMinimal'),
    t('settings.notifications.frequencyCaptionsLow'),
    t('settings.notifications.frequencyCaptionsBalanced'),
    t('settings.notifications.frequencyCaptionsHigh'),
    t('settings.notifications.frequencyCaptionsMaximum')
  ]

  return (
    <>
      <SettingRow
        icon={Bell}
        dot={notifOn ? 'on' : 'off'}
        title={t('settings.notifications.title')}
        subtitle={t('settings.notifications.subtitle')}
        keywords="proactive notifications master enable assistants"
        control={
          <Toggle
            on={notifOn}
            onChange={(on) => patch({ notificationsEnabled: on })}
            disabled={!settings}
            label={t('settings.notifications.title')}
          />
        }
      />

      <SettingRow
        icon={Gauge}
        title={t('settings.notifications.frequencyTitle')}
        subtitle={t('settings.notifications.frequencySubtitle')}
        keywords="frequency rate throttle interval off minimal low balanced high maximum"
        note={
          level === 0 ? (
            <span className="text-xs text-amber-400/90">
              {t('settings.notifications.frequencyOffNote')}
            </span>
          ) : undefined
        }
      >
        <div className="space-y-2">
          <div className="flex items-baseline justify-between text-sm">
            <span className="font-medium text-text-primary">{FREQUENCY_LABELS[level]}</span>
            <span className="text-text-tertiary">{FREQUENCY_CAPTIONS[level]}</span>
          </div>
          <Slider
            value={level}
            onChange={(v) => patch({ notificationFrequency: v })}
            min={0}
            max={5}
            step={1}
            ticks={[0, 1, 2, 3, 4, 5]}
            ariaLabel={t('settings.notifications.frequencySliderLabel')}
            disabled={!settings}
            leftLabel={<span className="text-xs">{t('settings.notifications.frequencyOff')}</span>}
            rightLabel={<span className="text-xs">{t('settings.notifications.frequencyMax')}</span>}
          />
        </div>
      </SettingRow>

      <SettingRow
        icon={Focus}
        dot={settings && settings.focusNotificationsEnabled && notifOn ? 'on' : 'off'}
        title={t('settings.notifications.focusTitle')}
        subtitle={t('settings.notifications.focusSubtitle')}
        keywords="focus notifications distraction refocus"
        note={
          <span className="text-xs text-text-tertiary">
            {t('settings.notifications.focusNote')}
          </span>
        }
        control={
          <Toggle
            on={!!settings?.focusNotificationsEnabled}
            onChange={(on) => patch({ focusNotificationsEnabled: on })}
            disabled={subDisabled}
            label={t('settings.notifications.focusTitle')}
          />
        }
      />

      <SettingRow
        icon={Brain}
        dot={settings && settings.memoryEnabled && notifOn ? 'on' : 'off'}
        title={t('settings.notifications.memoriesTitle')}
        subtitle={t('settings.notifications.memoriesSubtitle')}
        keywords="memory notifications extraction screen facts memories synth"
        control={
          <Toggle
            on={!!settings?.memoryEnabled}
            onChange={(on) => patch({ memoryEnabled: on })}
            disabled={subDisabled}
            label={t('settings.notifications.memoriesTitle')}
          />
        }
      />

      <SettingRow
        icon={Sparkles}
        dot={settings && settings.glowOverlayEnabled && notifOn ? 'on' : 'off'}
        title={t('settings.notifications.glowTitle')}
        subtitle={t('settings.notifications.glowSubtitle')}
        keywords="focus glow ring overlay halo distraction"
        control={
          <Toggle
            on={!!settings?.glowOverlayEnabled}
            onChange={(on) => patch({ glowOverlayEnabled: on })}
            disabled={subDisabled}
            label={t('settings.notifications.glowTitle')}
          />
        }
      />

      <SettingRow
        icon={Lightbulb}
        title={t('settings.notifications.insightsTitle')}
        subtitle={t('settings.notifications.insightsSubtitle')}
        keywords="insights proactive suggestion notification rewind"
      />
    </>
  )
}
