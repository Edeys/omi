import { useState } from 'react'
import { User, LogOut } from 'lucide-react'
import { auth, signOutUser } from '../../../lib/firebase'
import { getPreferences, setPreferences } from '../../../lib/preferences'
import { setDisplayName } from '../../../lib/userProfile'
import { toast } from '../../../lib/toast'
import { SettingRow } from '../SettingRow'
import { useTranslation } from '../../../i18n'

export function AccountTab(): React.JSX.Element {
  const prefs = getPreferences()
  const [name, setName] = useState(prefs.displayName ?? '')
  const { t } = useTranslation()

  // Transcription language moved to Settings → Transcription (Mac parity); this
  // row now owns only the display name.
  const saveProfile = (): void => {
    setPreferences({ displayName: name.trim() })
    void setDisplayName(name.trim()).catch(() =>
      toast(t('settings.account.nameSyncFailed'), { tone: 'warn' })
    )
    toast(t('settings.account.profileSaved'), { tone: 'success' })
  }

  return (
    <>
      <SettingRow
        icon={User}
        title={t('settings.account.profileTitle')}
        subtitle={t('settings.account.profileSubtitle')}
        keywords="name profile display"
      >
        <div className="space-y-3">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t('settings.account.namePlaceholder')}
            className="glass-subtle w-full rounded-lg px-4 py-3 text-sm text-text-secondary focus:outline-none"
          />
          <button onClick={saveProfile} className="btn-ghost">
            {t('settings.account.save')}
          </button>
        </div>
      </SettingRow>
      <SettingRow
        icon={LogOut}
        title={t('settings.account.signedInTitle')}
        subtitle={auth.currentUser?.email ?? t('settings.account.notSignedIn')}
        keywords="account email sign out logout"
        control={
          <button onClick={signOutUser} className="btn-ghost">
            {t('settings.account.signOut')}
          </button>
        }
      />
    </>
  )
}
