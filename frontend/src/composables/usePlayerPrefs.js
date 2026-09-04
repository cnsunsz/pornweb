import { reactive, watch } from 'vue'

/** Mirror Android SharedPreferences name `pw_player` (PlayerPrefs.kt). */
const STORAGE_KEY = 'pw_player'

const DEFAULTS = {
  defaultSpeed: 1.0,
  longPressSpeed: 2.0,
  skipSeconds: 10,
  swipeSeekSeconds: 90,
  doubleTapSeek: true,
  leftLongPressRewind: true,
  /** Web stand-in for Android `startLandscape`: auto-enter fullscreen on open. */
  autoFullscreen: false,
  resumeOnOpen: true,
}

function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULTS }
    const parsed = JSON.parse(raw)
    return { ...DEFAULTS, ...parsed }
  } catch {
    return { ...DEFAULTS }
  }
}

const prefs = reactive(load())

watch(
  prefs,
  (v) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...v }))
    } catch {}
  },
  { deep: true }
)

export function usePlayerPrefs() {
  return prefs
}

export { DEFAULTS, STORAGE_KEY }
