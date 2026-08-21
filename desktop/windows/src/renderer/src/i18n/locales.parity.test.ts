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
    // Brand / native language names are intentionally identical across locales.
    const allowIdentical = new Set([
      'app.name',
      'common.english',
      'common.vietnamese',
      'settings.agents.claudeTitle',
      'settings.agents.apiKeyPlaceholderEmpty',
      'settings.advanced.chatgpt',
      'settings.advanced.claude',
      'settings.advanced.exportSuccessLocation',
      'settings.about.versionName',
      'settings.about.updateErrorMessage',
      'home.hub.header.discord',
      'home.hub.chatHistory.defaultAssistant',
      'memories.showingFirstManageSuffix',
      'memories.toasts.deleteFailedSuffix',
      'onboarding.language.english',
      'onboarding.howDidYouHear.sources.productHunt',
      'onboarding.howDidYouHear.sources.youtube',
      'onboarding.howDidYouHear.sources.podcast',
      'onboarding.dataSources.chatgpt.title',
      'onboarding.dataSources.claude.title',
      'onboarding.dataSources.email.title',
      'conversationDetail.local.omi',
      'bar.pill.omi',
      'insightToast.whatsNew'
    ])
    const check = (
      enObj: Record<string, unknown>,
      viObj: Record<string, unknown>,
      prefix: string
    ): void => {
      for (const k of Object.keys(enObj)) {
        const enV = enObj[k]
        const viV = viObj[k]
        if (typeof enV === 'object' && enV !== null) {
          check(enV as Record<string, unknown>, viV as Record<string, unknown>, `${prefix}${k}.`)
        } else {
          expect(String(viV).trim().length, `${prefix}${k}`).toBeGreaterThan(0)
          if (!allowIdentical.has(`${prefix}${k}`)) {
            expect(String(viV), `${prefix}${k}`).not.toBe(String(enV))
          }
        }
      }
    }
    check(en, vi, '')
  })
})
