import { createI18n } from 'vue-i18n'
import zhCN from './zh-CN'
import zhTW from './zh-TW'
import en from './en'
import ja from './ja'

export const SUPPORTED = [
  { code: 'zh-CN', label: '简体中文' },
  { code: 'zh-TW', label: '繁體中文' },
  { code: 'en', label: 'English' },
  { code: 'ja', label: '日本語' },
]

export function detectLocale() {
  const saved = localStorage.getItem('mv_lang')
  if (saved && ['zh-CN', 'zh-TW', 'en', 'ja'].includes(saved)) return saved
  const n = (navigator.language || navigator.userLanguage || 'en').toLowerCase()
  if (n.startsWith('zh-tw') || n.startsWith('zh-hk') || n.startsWith('zh-mo') || n.includes('hant')) return 'zh-TW'
  if (n.startsWith('zh')) return 'zh-CN'
  if (n.startsWith('ja')) return 'ja'
  if (n.startsWith('en')) return 'en'
  return 'en'
}

export const i18n = createI18n({
  legacy: false,
  locale: detectLocale(),
  fallbackLocale: 'en',
  messages: { 'zh-CN': zhCN, 'zh-TW': zhTW, en, ja },
})

export function setLocale(code) {
  if (!['zh-CN', 'zh-TW', 'en', 'ja'].includes(code)) return
  i18n.global.locale.value = code
  localStorage.setItem('mv_lang', code)
  document.documentElement.lang = code
}

export function apiError(e, t) {
  const d = e?.response?.data?.detail
  if (typeof d === 'string' && t) {
    const key = 'api.' + d
    const translated = t(key)
    if (translated && translated !== key) return translated
    return d
  }
  return t ? t('err.fail') : 'Error'
}
