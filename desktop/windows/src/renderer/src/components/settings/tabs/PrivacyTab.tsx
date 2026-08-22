import { useEffect, useState } from 'react'
import { Activity, EyeOff, Monitor, ShieldCheck } from 'lucide-react'
import { SettingRow } from '../SettingRow'
import { Toggle } from '../Toggle'
import { useTranslation } from '../../../i18n'
import type { UsageSettings } from '../../../../../shared/types'

export function PrivacyTab(): React.JSX.Element {
  const [usage, setUsage] = useState<UsageSettings | null>(null)
  const { t } = useTranslation()
  useEffect(() => {
    window.omi
      .usageGetSettings()
      .then(setUsage)
      .catch(() => setUsage(null))
  }, [])
  const saveUsage = async (next: UsageSettings): Promise<void> => {
    setUsage(await window.omi.usageSetSettings(next))
  }

  // Bar/HUD screen-share privacy: exclude the top-edge bar from captures
  // (WDA_EXCLUDEFROMCAPTURE). Persisted in main's app settings; applied live.
  const [hudProtected, setHudProtected] = useState<boolean | null>(null)
  useEffect(() => {
    window.omiBar
      .getContentProtection()
      .then(setHudProtected)
      .catch(() => setHudProtected(null))
  }, [])
  const toggleHudProtection = (on: boolean): void => {
    setHudProtected(on)
    void window.omiBar.setContentProtection(on).then(setHudProtected)
  }

  // "Screen Sharing in Chat" (Mac's chatScreenshotSharingEnabled, default ON).
  // The consent gate for the model-invoked capture_screen tool: on → Omi may
  // capture the screen when you ask about it; off → the tool is refused. Turning
  // it on captures nothing by itself — it only permits the tool.
  const [screenShareInChat, setScreenShareInChat] = useState<boolean | null>(null)
  useEffect(() => {
    window.omi
      .getChatScreenshotSharing()
      .then(setScreenShareInChat)
      .catch(() => setScreenShareInChat(null))
  }, [])
  const toggleScreenShareInChat = (on: boolean): void => {
    setScreenShareInChat(on)
    void window.omi.setChatScreenshotSharing(on).then(setScreenShareInChat)
  }

  return (
    <>
      <SettingRow
        icon={Activity}
        dot={usage?.enabled ? 'on' : 'off'}
        title={t('settings.privacy.trackingTitle')}
        subtitle={t('settings.privacy.trackingSubtitle')}
        keywords="usage foreground app tracking privacy"
        control={
          <Toggle
            on={!!usage?.enabled}
            onChange={(on) => usage && void saveUsage({ ...usage, enabled: on })}
            disabled={!usage}
            label={t('settings.privacy.trackingTitle')}
          />
        }
      >
        {usage?.enabled && (
          <label className="flex items-center gap-2 text-sm text-text-secondary">
            <span>{t('settings.privacy.retentionLabel')}</span>
            <select
              value={usage.retentionDays}
              onChange={(e) => void saveUsage({ ...usage, retentionDays: Number(e.target.value) })}
              className="rounded-md bg-white/10 px-3 py-1.5 text-sm text-white focus:outline-none"
            >
              <option value={30} className="bg-neutral-900">
                {t('settings.privacy.retention30')}
              </option>
              <option value={45} className="bg-neutral-900">
                {t('settings.privacy.retention45')}
              </option>
              <option value={60} className="bg-neutral-900">
                {t('settings.privacy.retention60')}
              </option>
              <option value={90} className="bg-neutral-900">
                {t('settings.privacy.retention90')}
              </option>
              <option value={180} className="bg-neutral-900">
                {t('settings.privacy.retention180')}
              </option>
            </select>
          </label>
        )}
      </SettingRow>
      <SettingRow
        icon={EyeOff}
        dot={hudProtected ? 'on' : 'off'}
        title={t('settings.privacy.hideBarTitle')}
        subtitle={t('settings.privacy.hideBarSubtitle')}
        keywords="bar hud screen share capture protection privacy exclude recording"
        control={
          <Toggle
            on={!!hudProtected}
            onChange={toggleHudProtection}
            disabled={hudProtected === null}
            label={t('settings.privacy.hideBarTitle')}
          />
        }
      />
      <SettingRow
        icon={Monitor}
        dot={screenShareInChat ? 'on' : 'off'}
        title={t('settings.privacy.screenShareTitle')}
        subtitle={t('settings.privacy.screenShareSubtitle')}
        keywords="screen sharing chat capture screenshot ask omi see my screen vision"
        control={
          <Toggle
            on={!!screenShareInChat}
            onChange={toggleScreenShareInChat}
            disabled={screenShareInChat === null}
            label={t('settings.privacy.screenShareTitle')}
          />
        }
      />
      <SettingRow
        icon={ShieldCheck}
        title={t('settings.privacy.onDeviceTitle')}
        subtitle={t('settings.privacy.onDeviceSubtitle')}
        keywords="privacy local data on-device cloud"
      />
    </>
  )
}
