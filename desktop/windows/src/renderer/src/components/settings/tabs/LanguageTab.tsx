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
