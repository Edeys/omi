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
