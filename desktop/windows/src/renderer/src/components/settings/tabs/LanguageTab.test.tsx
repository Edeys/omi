// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { LanguageTab } from './LanguageTab'
import { changeUiLanguage } from '../../../i18n'
import { getPreferences } from '../../../lib/preferences'
import { SettingsSearchProvider } from '../SettingsSearchProvider'

afterEach(cleanup)

vi.mock('../../../i18n', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../i18n')>()
  return { ...actual, changeUiLanguage: vi.fn() }
})

describe('LanguageTab', () => {
  it('renders a language selector with English and Vietnamese options', () => {
    render(
      <SettingsSearchProvider>
        <LanguageTab />
      </SettingsSearchProvider>
    )
    expect(screen.getByRole('combobox')).toBeTruthy()
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual([
      'English',
      'Tiếng Việt'
    ])
  })

  it('switching to Vietnamese calls changeUiLanguage with "vi"', () => {
    render(
      <SettingsSearchProvider>
        <LanguageTab />
      </SettingsSearchProvider>
    )
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'vi' } })
    expect(changeUiLanguage).toHaveBeenCalledWith('vi')
  })

  it('shows the persisted language as the current selection', () => {
    render(
      <SettingsSearchProvider>
        <LanguageTab />
      </SettingsSearchProvider>
    )
    expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe('en')
    expect(getPreferences().uiLanguage ?? 'en').toBe('en')
  })
})
