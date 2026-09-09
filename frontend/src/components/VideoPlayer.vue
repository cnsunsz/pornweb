<template>
  <div
    ref="playerEl"
    class="player"
    :class="{ fullscreen: isFullscreen, 'controls-visible': controlsVisible, paused: isPaused }"
    @mousemove="onSurfaceMove"
    @mouseleave="onSurfaceLeave"
    @mousedown="onSurfaceDown"
    @mouseup="onSurfaceUp"
    @touchstart.passive="onTouchStart"
    @touchend="onTouchEnd"
    @touchmove.passive="onTouchMove"
  >
    <video
      ref="videoEl"
      :src="src"
      preload="auto"
      @loadedmetadata="onLoaded"
      @timeupdate="onTimeUpdate"
      @play="isPaused = false"
      @pause="isPaused = true"
      @ended="onEnded"
      @volumechange="onVolumeChange"
      @waiting="isBuffering = true"
      @canplay="isBuffering = false"
      @error="onError"
    />

    <div v-if="isBuffering && !playError" class="buffering">
      <div class="spinner"></div>
    </div>

    <div v-if="playError" class="play-error" @click.stop>
      <div class="play-error-msg">{{ playError }}</div>
      <button class="play-error-btn" @click="retryPlay">{{ t('player.retry') }}</button>
    </div>

    <div v-if="isPaused && !isBuffering" class="center-play" @click.stop="togglePlay">
      <svg viewBox="0 0 24 24" width="72" height="72"><path d="M8 5v14l11-7z" fill="white"/></svg>
    </div>

    <!-- Gesture feedback (double-tap / swipe / long-press) -->
    <div v-if="gestureHint" class="gesture-hint">{{ gestureHint }}</div>
    <div v-if="speedBoosting" class="speed-badge">{{ prefs.longPressSpeed }}x</div>

    <div class="top-bar" @click.stop>
      <button class="icon-btn" @click="$emit('close')" :title="t('player.back')">
        <svg viewBox="0 0 24 24" width="24" height="24"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z" fill="white"/></svg>
      </button>
      <span class="title">{{ title }}</span>
      <div class="top-right">
        <button class="icon-btn" @click="openPlaybackSettings" :title="t('playback.title')">
          <svg viewBox="0 0 24 24" width="22" height="22"><path d="M19.14 12.94c.04-.31.06-.63.06-.94s-.02-.63-.06-.94l2.03-1.58a.49.49 0 0 0 .12-.61l-1.92-3.32a.49.49 0 0 0-.59-.22l-2.39.96a7.05 7.05 0 0 0-1.62-.94l-.36-2.54A.49.49 0 0 0 13.9 2h-3.8a.49.49 0 0 0-.48.41l-.36 2.54c-.59.24-1.13.55-1.62.94l-2.39-.96a.49.49 0 0 0-.59.22L2.74 8.87a.48.48 0 0 0 .12.61l2.03 1.58c-.04.31-.06.63-.06.94s.02.63.06.94L2.86 14.53a.49.49 0 0 0-.12.61l1.92 3.32c.12.22.39.3.59.22l2.39-.96c.5.39 1.04.71 1.62.94l.36 2.54c.05.24.24.41.48.41h3.8c.24 0 .44-.17.48-.41l.36-2.54c.59-.24 1.13-.55 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32a.49.49 0 0 0-.12-.61l-2.01-1.58zM12 15.6A3.6 3.6 0 1 1 12 8.4a3.6 3.6 0 0 1 0 7.2z" fill="white"/></svg>
        </button>
      </div>
    </div>

    <div class="bottom-bar" @click.stop>
      <div
        class="progress-container"
        ref="progressEl"
        @mousedown="startSeek"
        @mousemove="onProgressHover"
        @mouseleave="hoverTime = null"
      >
        <div class="progress-bg">
          <div class="progress-buffered" :style="{ width: bufferedPercent + '%' }"></div>
          <div class="progress-played" :style="{ width: playedPercent + '%' }">
            <div class="progress-thumb"></div>
          </div>
        </div>
        <div v-if="hoverTime !== null" class="hover-tooltip" :style="{ left: hoverX + 'px' }">
          {{ formatTime(hoverTime) }}
        </div>
      </div>

      <div class="controls-row">
        <div class="controls-left">
          <button class="icon-btn" @click.stop="togglePlay" :title="isPaused ? t('player.play') : t('player.pause')">
            <svg v-if="isPaused" viewBox="0 0 24 24" width="28" height="28"><path d="M8 5v14l11-7z" fill="white"/></svg>
            <svg v-else viewBox="0 0 24 24" width="28" height="28"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" fill="white"/></svg>
          </button>

          <button class="icon-btn" @click.stop="skip(-prefs.skipSeconds)" :title="t('player.backN', { n: prefs.skipSeconds })">
            <svg viewBox="0 0 24 24" width="22" height="22"><path d="M11.99 5V1l-5 5 5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6h-2c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z" fill="white"/><text x="7.5" y="16" font-size="6.5" fill="white" font-weight="bold">{{ prefs.skipSeconds }}</text></svg>
          </button>

          <button class="icon-btn" @click.stop="skip(prefs.skipSeconds)" :title="t('player.fwdN', { n: prefs.skipSeconds })">
            <svg viewBox="0 0 24 24" width="22" height="22"><path d="M12.01 5V1l5 5-5 5V7c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6h2c0 4.42-3.58 8-8 8s-8-3.58-8-8 3.58-8 8-8z" fill="white"/><text x="7.5" y="16" font-size="6.5" fill="white" font-weight="bold">{{ prefs.skipSeconds }}</text></svg>
          </button>

          <div class="volume-group" @click.stop>
            <button class="icon-btn" @click="toggleMute" :title="isMuted ? t('player.unmute') : t('player.mute')">
              <svg v-if="isMuted || volume === 0" viewBox="0 0 24 24" width="22" height="22"><path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z" fill="white"/></svg>
              <svg v-else-if="volume < 0.5" viewBox="0 0 24 24" width="22" height="22"><path d="M18.5 12c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM5 9v6h4l5 5V4L9 9H5z" fill="white"/></svg>
              <svg v-else viewBox="0 0 24 24" width="22" height="22"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" fill="white"/></svg>
            </button>
            <div class="volume-slider-wrap">
              <input type="range" class="volume-slider" min="0" max="1" step="0.01"
                :value="isMuted ? 0 : volume"
                @input="setVolume($event.target.value)"
              />
            </div>
          </div>

          <span class="time-display">
            {{ formatTime(currentTime) }} / {{ formatTime(duration) }}
          </span>
        </div>

        <div class="controls-right">
          <div v-if="parts && parts.length > 1" class="parts-group" @click.stop>
            <button
              v-for="(p, i) in parts"
              :key="i"
              class="icon-btn speed-btn"
              :class="{ active: part === i }"
              @click="switchPart(i)"
            >{{ p.label || (i+1) }}</button>
          </div>

          <div class="speed-group" @click.stop>
            <button class="icon-btn speed-btn" @click="cycleSpeed">
              {{ playbackRate }}x
            </button>
          </div>


          <div class="sub-group" @click.stop>
            <button class="icon-btn" :class="{ active: !!selectedSubId }" @click="subMenuOpen = !subMenuOpen" :title="t('player.subtitles')">
              <svg viewBox="0 0 24 24" width="22" height="22"><path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zM4 12h4v2H4v-2zm10 6H4v-2h10v2zm6 0h-4v-2h4v2zm0-4H10v-2h10v2z" fill="white"/></svg>
            </button>
            <div v-if="subMenuOpen" class="sub-menu">
              <div class="sub-menu-title">{{ t('player.subtitles') }}</div>
              <button class="sub-item" :class="{ active: !selectedSubId }" @click="selectSubtitle(null)">{{ t('player.subOff') }}</button>
              <button
                v-for="tr in subtitleTracks"
                :key="tr.id"
                class="sub-item"
                :class="{ active: selectedSubId === tr.id, preparing: subPreparingId === tr.id }"
                :disabled="tr.supported === false"
                @click="selectSubtitle(tr.id)"
              >
                <span class="sub-label">{{ tr.label }}</span>
                <span class="sub-meta">
                  <template v-if="subPreparingId === tr.id">{{ t('player.subPreparingShort') }}</template>
                  <template v-else>{{ tr.source === 'embedded' ? (tr.cached ? '内嵌·已缓存' : '内嵌') : '外挂' }}</template>
                </span>
              </button>
              <div v-if="!subtitleTracks.length" class="sub-empty">{{ subLoading ? t('player.subLoading') : t('player.subNone') }}</div>
            </div>
          </div>

          <button class="icon-btn" @click.stop="togglePiP" :title="t('player.pip')">
            <svg viewBox="0 0 24 24" width="22" height="22"><path d="M19 11h-8v6h8v-6zm4 8V4.98C23 3.88 22.1 3 21 3H3c-1.1 0-2 .88-2 1.98V19c0 1.1.9 2 2 2h18c1.1 0 2-.9 2-2zm-2 .02H3V4.97h18v14.05z" fill="white"/></svg>
          </button>

          <button class="icon-btn" @click.stop="toggleFullscreen" :title="isFullscreen ? t('player.exitFs') : t('player.fs')">
            <svg v-if="!isFullscreen" viewBox="0 0 24 24" width="22" height="22"><path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z" fill="white"/></svg>
            <svg v-else viewBox="0 0 24 24" width="22" height="22"><path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z" fill="white"/></svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { saveProgress, getSubtitles, getSubtitleUrl, getWebStreamUrl, fetchSubtitleAsync, getSubtitleStatus } from '@/api/media'
import { usePlayerPrefs } from '@/composables/usePlayerPrefs'

const { t } = useI18n()
const router = useRouter()
const prefs = usePlayerPrefs()

const props = defineProps({
  src: { type: String, required: true },
  title: { type: String, default: '' },
  mediaId: { type: Number, default: null },
  part: { type: Number, default: 0 },
  parts: { type: Array, default: () => [] },
  webRemux: { type: Boolean, default: false },
  audioCodec: { type: String, default: '' },
  mediaDuration: { type: Number, default: 0 },
})

const emit = defineEmits(['close', 'part'])

const playerEl = ref(null)
const videoEl = ref(null)
const progressEl = ref(null)

const isPaused = ref(true)
const isBuffering = ref(false)
const playError = ref('')
const isFullscreen = ref(false)
const isMuted = ref(false)
const volume = ref(1)
const currentTime = ref(0)
const duration = ref(0)
const bufferedPercent = ref(0)
const playedPercent = ref(0)
const playbackRate = ref(1)
const controlsVisible = ref(true)
const hoverTime = ref(null)
const hoverX = ref(0)
const gestureHint = ref('')
const speedBoosting = ref(false)

let controlsTimer = null
let seeking = false
let lastSave = 0
let baseRate = 1
let spaceHeld = false
let longPressTimer = null
let longPressActive = false
let longPressSide = null
let rewindTimer = null
let lastTap = { t: 0, x: 0 }
let dragSeek = null // { startX, startTime, width }
let hintTimer = null
let suppressClickUntil = 0
let pointerDownAt = null
let remuxBaseStart = 0
let remuxReloading = false

const SPEEDS = [0.75, 1, 1.25, 1.5, 2]

function showControls() {
  controlsVisible.value = true
  clearTimeout(controlsTimer)
  controlsTimer = setTimeout(() => {
    if (!isPaused.value) controlsVisible.value = false
  }, 3000)
}
function hideControlsDelayed() {
  clearTimeout(controlsTimer)
  controlsTimer = setTimeout(() => {
    if (!isPaused.value) controlsVisible.value = false
  }, 1500)
}

function flashHint(text) {
  gestureHint.value = text
  clearTimeout(hintTimer)
  hintTimer = setTimeout(() => { gestureHint.value = '' }, 900)
}

function togglePlay() {
  if (Date.now() < suppressClickUntil) return
  if (!videoEl.value) return
  if (videoEl.value.paused) videoEl.value.play()
  else videoEl.value.pause()
}

function skip(sec) {
  if (!videoEl.value) return
  if (props.webRemux) {
    const abs = Math.max(0, Math.min(duration.value || 1e12, remuxAbsoluteTime() + sec))
    reloadRemuxAt(abs)
    showControls()
    return
  }
  videoEl.value.currentTime = Math.max(0, Math.min(duration.value, videoEl.value.currentTime + sec))
  showControls()
}

function setVolume(v) {
  if (!videoEl.value) return
  videoEl.value.volume = parseFloat(v)
  volume.value = parseFloat(v)
  isMuted.value = v == 0
  videoEl.value.muted = isMuted.value
}
function toggleMute() {
  if (!videoEl.value) return
  isMuted.value = !isMuted.value
  videoEl.value.muted = isMuted.value
}

function applyRate(rate) {
  playbackRate.value = rate
  if (videoEl.value) videoEl.value.playbackRate = rate
}

function cycleSpeed() {
  const idx = SPEEDS.indexOf(playbackRate.value)
  const next = SPEEDS[(idx + 1) % SPEEDS.length]
  baseRate = next
  applyRate(next)
}

function toggleFullscreen() {
  if (!playerEl.value) return
  if (!document.fullscreenElement) {
    playerEl.value.requestFullscreen?.() || playerEl.value.webkitRequestFullscreen?.()
    isFullscreen.value = true
  } else {
    document.exitFullscreen?.()
    isFullscreen.value = false
  }
}

function togglePiP() {
  if (!videoEl.value) return
  if (document.pictureInPictureElement) document.exitPictureInPicture()
  else videoEl.value.requestPictureInPicture()
}

function openPlaybackSettings() {
  emit('close')
  router.push({ path: '/settings', query: { tab: 'playback' } })
}

function startSeek(e) {
  seeking = true
  seekTo(e)
  document.addEventListener('mousemove', onSeekMove)
  document.addEventListener('mouseup', stopSeek)
}
function onSeekMove(e) { if (seeking) seekTo(e) }
function stopSeek() {
  seeking = false
  document.removeEventListener('mousemove', onSeekMove)
  document.removeEventListener('mouseup', stopSeek)
}
function remuxAbsoluteTime() {
  return remuxBaseStart + (videoEl.value?.currentTime || 0)
}

function reloadRemuxAt(absSec) {
  if (!props.mediaId || remuxReloading) return
  remuxReloading = true
  isBuffering.value = true
  playError.value = ''
  remuxBaseStart = Math.max(0, absSec)
  const url = getWebStreamUrl(props.mediaId, props.part || 0, remuxBaseStart)
  const v = videoEl.value
  if (!v) { remuxReloading = false; return }
  v.src = url
  v.load()
  v.play().catch(() => {}).finally(() => { remuxReloading = false })
}

function seekTo(e) {
  if (!progressEl.value || !videoEl.value) return
  const rect = progressEl.value.getBoundingClientRect()
  const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  const target = pct * duration.value
  if (props.webRemux) {
    // fMP4 pipe cannot byte-seek; restart ffmpeg at timestamp (Emby-style)
    reloadRemuxAt(target)
    return
  }
  videoEl.value.currentTime = target
}
function onProgressHover(e) {
  if (!progressEl.value) return
  const rect = progressEl.value.getBoundingClientRect()
  const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  hoverTime.value = pct * duration.value
  hoverX.value = e.clientX - rect.left
}

function onLoaded() {
  playError.value = ''
  const d = videoEl.value.duration
  if (d && isFinite(d) && d > 0 && !props.webRemux) {
    duration.value = d
  } else if (d && isFinite(d) && d > 0 && props.webRemux && !duration.value) {
    duration.value = remuxBaseStart + d
  }
  // Prefer server-known duration from localStorage progress payload if present
  try {
    const kd = localStorage.getItem(props.mediaId ? `mv_dur_${props.mediaId}` : '')
    if (kd && Number(kd) > 0) duration.value = Number(kd)
  } catch {}
  baseRate = prefs.defaultSpeed
  applyRate(prefs.defaultSpeed)
  if (prefs.resumeOnOpen && !props.webRemux) {
    const saved = getSavedPosition()
    if (saved > 0 && saved < (duration.value || Infinity) - 3) {
      videoEl.value.currentTime = saved
    }
  } else if (prefs.resumeOnOpen && props.webRemux && remuxBaseStart === 0) {
    const saved = getSavedPosition()
    if (saved > 5 && saved < (duration.value || Infinity) - 3) {
      reloadRemuxAt(saved)
      return
    }
  }
  const savedVol = localStorage.getItem('mv_volume')
  if (savedVol !== null) setVolume(parseFloat(savedVol))
  videoEl.value.play().catch(() => {})
  if (prefs.autoFullscreen && !document.fullscreenElement) {
    setTimeout(() => {
      try { toggleFullscreen() } catch {}
    }, 50)
  }
}
function onTimeUpdate() {
  if (!videoEl.value || seeking) return
  if (props.webRemux) {
    currentTime.value = remuxAbsoluteTime()
    // fMP4 pipe often has infinite/unknown duration — keep last known if finite
    const d = videoEl.value.duration
    if (d && isFinite(d) && d > 0) {
      // relative duration from this segment only; prefer saved media duration
      if (!duration.value || duration.value < remuxBaseStart + d) {
        // leave duration if already set from metadata / progress
      }
    }
  } else {
    currentTime.value = videoEl.value.currentTime
    duration.value = videoEl.value.duration || 0
  }
  playedPercent.value = duration.value ? (currentTime.value / duration.value) * 100 : 0
  if (videoEl.value.buffered.length > 0 && duration.value) {
    const end = videoEl.value.buffered.end(videoEl.value.buffered.length - 1)
    const absEnd = props.webRemux ? remuxBaseStart + end : end
    bufferedPercent.value = (absEnd / duration.value) * 100
  }
  savePosition()
}
function onVolumeChange() {
  if (!videoEl.value) return
  volume.value = videoEl.value.volume
  isMuted.value = videoEl.value.muted
  localStorage.setItem('mv_volume', String(volume.value))
}
function onEnded() {
  isPaused.value = true
  clearSavedPosition()
}
function onError() {
  isBuffering.value = false
  const err = videoEl.value?.error
  const code = err?.code
  const ac = (props.audioCodec || '').toLowerCase()
  const risky = ['eac3', 'ac3', 'dts', 'truehd', 'mlp'].includes(ac)
  // 3=DECODE, 4=SRC_NOT_SUPPORTED — often unsupported audio (E-AC3/DTS/TrueHD) in MKV
  if (code === 3 || code === 4 || risky) {
    if (props.webRemux) {
      playError.value = t('player.remuxError')
    } else {
      playError.value = t('player.decodeError')
    }
  } else if (code) {
    playError.value = t('player.playError')
  } else {
    playError.value = t('player.playError')
  }
}
function retryPlay() {
  playError.value = ''
  isBuffering.value = true
  if (videoEl.value) {
    videoEl.value.load()
    videoEl.value.play().catch(() => {})
  }
}

function getStorageKey() { return props.mediaId ? `mv_pos_${props.mediaId}` : '' }
function savePosition() {
  const key = getStorageKey()
  if (key && currentTime.value > 5) {
    localStorage.setItem(key, String(Math.floor(currentTime.value)))
  }
  if (props.mediaId && duration.value > 0) {
    localStorage.setItem(`mv_dur_${props.mediaId}`, String(Math.floor(duration.value)))
  }
  const now = Date.now()
  if (props.mediaId && now - lastSave > 4000) {
    lastSave = now
    saveProgress(props.mediaId, {
      position: currentTime.value,
      duration: duration.value || 0,
      part: props.part || 0
    }).catch(() => {})
  }
}
function getSavedPosition() {
  const key = getStorageKey()
  if (!key) return 0
  return parseFloat(localStorage.getItem(key) || '0')
}
function clearSavedPosition() {
  const key = getStorageKey()
  if (key) localStorage.removeItem(key)
}

/** Skip shortcuts when focus is in form fields or Element Plus overlays. */
function isTypingTarget(el) {
  if (!el || el === document.body) return false
  const tag = (el.tagName || '').toLowerCase()
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return true
  if (el.isContentEditable) return true
  if (el.closest?.('.el-dialog, .el-message-box, .el-overlay, .el-select-dropdown, .el-picker-panel')) return true
  return false
}

function beginSpeedBoost() {
  if (!videoEl.value || speedBoosting.value) return
  speedBoosting.value = true
  applyRate(prefs.longPressSpeed)
  if (videoEl.value.paused) videoEl.value.play().catch(() => {})
}
function endSpeedBoost() {
  if (!speedBoosting.value) return
  speedBoosting.value = false
  applyRate(baseRate)
}
function beginRewind() {
  if (rewindTimer) return
  // HTML video cannot play negative rate; tick seek-back while held.
  rewindTimer = setInterval(() => {
    skip(-Math.max(1, prefs.skipSeconds / 2))
  }, 200)
  flashHint(`« ${prefs.skipSeconds}s`)
}
function endRewind() {
  if (rewindTimer) {
    clearInterval(rewindTimer)
    rewindTimer = null
  }
}

function onKeydown(e) {
  if (isTypingTarget(e.target)) return
  const key = e.key
  if (key === ' ' || key === 'Spacebar') {
    e.preventDefault()
    if (!spaceHeld) {
      spaceHeld = true
      // Hold Space → temporary long-press speed; short tap still toggles play on keyup.
      longPressTimer = setTimeout(() => {
        beginSpeedBoost()
      }, 280)
    }
    return
  }
  switch (key) {
    case 'ArrowLeft':
      e.preventDefault()
      skip(-prefs.skipSeconds)
      flashHint(`- ${prefs.skipSeconds}s`)
      break
    case 'ArrowRight':
      e.preventDefault()
      skip(prefs.skipSeconds)
      flashHint(`+ ${prefs.skipSeconds}s`)
      break
    case 'ArrowUp':
      e.preventDefault()
      setVolume(Math.min(1, volume.value + 0.1))
      break
    case 'ArrowDown':
      e.preventDefault()
      setVolume(Math.max(0, volume.value - 0.1))
      break
    case 'f': case 'F':
      e.preventDefault()
      toggleFullscreen()
      break
    case 'm': case 'M':
      e.preventDefault()
      toggleMute()
      break
    case 'Escape':
      if (isFullscreen.value) toggleFullscreen()
      else emit('close')
      break
  }
}

function onKeyup(e) {
  if (e.key !== ' ' && e.key !== 'Spacebar') return
  if (!spaceHeld) return
  spaceHeld = false
  clearTimeout(longPressTimer)
  longPressTimer = null
  if (speedBoosting.value) {
    endSpeedBoost()
  } else {
    togglePlay()
  }
}

function clientXY(e) {
  if (e.touches && e.touches[0]) return { x: e.touches[0].clientX, y: e.touches[0].clientY }
  if (e.changedTouches && e.changedTouches[0]) return { x: e.changedTouches[0].clientX, y: e.changedTouches[0].clientY }
  return { x: e.clientX, y: e.clientY }
}

function sideFromX(x) {
  const rect = playerEl.value?.getBoundingClientRect()
  if (!rect) return 'right'
  return (x - rect.left) < rect.width / 2 ? 'left' : 'right'
}

function handleDoubleTap(x) {
  if (!prefs.doubleTapSeek) {
    toggleFullscreen()
    return
  }
  const side = sideFromX(x)
  const sec = prefs.skipSeconds
  if (side === 'left') {
    skip(-sec)
    flashHint(`- ${sec}s`)
  } else {
    skip(sec)
    flashHint(`+ ${sec}s`)
  }
  suppressClickUntil = Date.now() + 350
}

function onSurfaceDown(e) {
  if (e.button != null && e.button !== 0) return
  if (e.target.closest?.('.top-bar, .bottom-bar, .icon-btn, .progress-container, .center-play')) return
  const { x } = clientXY(e)
  pointerDownAt = { x, t: Date.now() }
  longPressSide = sideFromX(x)
  longPressActive = false
  clearTimeout(longPressTimer)
  longPressTimer = setTimeout(() => {
    longPressActive = true
    if (longPressSide === 'left' && prefs.leftLongPressRewind) beginRewind()
    else beginSpeedBoost()
  }, 400)
  // Horizontal drag seek: full width ≈ swipeSeekSeconds
  dragSeek = {
    startX: x,
    startTime: videoEl.value?.currentTime || 0,
    width: playerEl.value?.getBoundingClientRect().width || 1,
    moved: false,
  }
  showControls()
}

function onSurfaceMove(e) {
  showControls()
  if (!dragSeek || !videoEl.value) return
  if (longPressActive) return
  const { x } = clientXY(e)
  const dx = x - dragSeek.startX
  if (Math.abs(dx) < 8) return
  dragSeek.moved = true
  clearTimeout(longPressTimer)
  // pct of width * configured full-width seconds
  const delta = (dx / dragSeek.width) * prefs.swipeSeekSeconds
  const target = Math.max(0, Math.min(duration.value, dragSeek.startTime + delta))
  videoEl.value.currentTime = target
  flashHint(`${delta >= 0 ? '+' : ''}${Math.round(delta)}s`)
}

function onSurfaceLeave() {
  hideControlsDelayed()
}

function finishPointer(e) {
  clearTimeout(longPressTimer)
  longPressTimer = null
  if (longPressActive) {
    endSpeedBoost()
    endRewind()
    longPressActive = false
    suppressClickUntil = Date.now() + 300
    dragSeek = null
    pointerDownAt = null
    return
  }
  const { x } = clientXY(e)
  const moved = dragSeek?.moved
  dragSeek = null
  if (moved) {
    suppressClickUntil = Date.now() + 300
    pointerDownAt = null
    return
  }
  const now = Date.now()
  if (now - lastTap.t < 320 && Math.abs(x - lastTap.x) < 40) {
    handleDoubleTap(x)
    lastTap = { t: 0, x: 0 }
    pointerDownAt = null
    return
  }
  lastTap = { t: now, x }
  // Single tap → play/pause (after short delay so double-tap can cancel)
  setTimeout(() => {
    if (Date.now() - lastTap.t >= 300 && lastTap.t) {
      togglePlay()
      lastTap = { t: 0, x: 0 }
    }
  }, 300)
  pointerDownAt = null
}

function onSurfaceUp(e) {
  if (e.target.closest?.('.top-bar, .bottom-bar, .icon-btn, .progress-container')) {
    clearTimeout(longPressTimer)
    endSpeedBoost()
    endRewind()
    dragSeek = null
    return
  }
  finishPointer(e)
}

function onTouchStart(e) {
  if (e.target.closest?.('.top-bar, .bottom-bar, .icon-btn, .progress-container')) return
  onSurfaceDown(e)
}
function onTouchMove(e) { onSurfaceMove(e) }
function onTouchEnd(e) {
  if (e.target.closest?.('.top-bar, .bottom-bar, .icon-btn, .progress-container')) return
  finishPointer(e)
}


const subtitleTracks = ref([])
const selectedSubId = ref(null)
const subMenuOpen = ref(false)
const subLoading = ref(false)
const subPreparingId = ref(null)
let subSelectGen = 0
let subBlobUrl = null
let subPollTimer = null

function preferDefaultTrack(tracks) {
  // Only auto-enable cheap external sidecars. Embedded MKV extract on rclone
  // can take minutes and starves video Range reads (endless spinner) — match
  // Android: on-demand single track when user picks.
  const rank = (lang) => {
    const l = (lang || '').toLowerCase()
    if (l.startsWith('zh')) return 0
    if (l === 'en' || l.startsWith('en')) return 1
    if (l === 'ja') return 2
    return 9
  }
  const external = (tracks || []).filter((tr) => tr.source === 'external' && tr.supported !== false)
  if (!external.length) return null
  const sorted = [...external].sort((a, b) => rank(a.language) - rank(b.language))
  return sorted[0] || null
}

function revokeSubBlob() {
  if (subBlobUrl) {
    try { URL.revokeObjectURL(subBlobUrl) } catch {}
    subBlobUrl = null
  }
}

function stopSubPoll() {
  if (subPollTimer) {
    clearTimeout(subPollTimer)
    subPollTimer = null
  }
}

async function loadSubtitles() {
  if (!props.mediaId) {
    subtitleTracks.value = []
    selectedSubId.value = null
    await selectSubtitle(null)
    return
  }
  subLoading.value = true
  try {
    const { data } = await getSubtitles(props.mediaId, props.part || 0)
    subtitleTracks.value = data?.tracks || []
    const pref = preferDefaultTrack(subtitleTracks.value)
    if (pref) await selectSubtitle(pref.id)
    else await selectSubtitle(null)
  } catch {
    subtitleTracks.value = []
    await selectSubtitle(null)
  } finally {
    subLoading.value = false
  }
}

function clearVideoTracks() {
  const v = videoEl.value
  if (!v) return
  Array.from(v.querySelectorAll('track[data-pw-sub]')).forEach((el) => el.remove())
  if (v.textTracks) {
    for (let i = 0; i < v.textTracks.length; i++) {
      try { v.textTracks[i].mode = 'disabled' } catch {}
    }
  }
}

function attachVttBlob(vttText, meta) {
  const v = videoEl.value
  if (!v || !vttText) return
  clearVideoTracks()
  revokeSubBlob()
  const blob = new Blob([vttText], { type: 'text/vtt' })
  subBlobUrl = URL.createObjectURL(blob)
  const el = document.createElement('track')
  el.kind = 'subtitles'
  el.label = meta?.label || 'PornWeb'
  el.srclang = (meta?.language || 'zh').slice(0, 8)
  el.src = subBlobUrl
  el.default = true
  el.setAttribute('data-pw-sub', '1')
  const show = () => {
    try { if (el.track) el.track.mode = 'showing' } catch {}
  }
  el.addEventListener('load', show)
  v.appendChild(el)
  setTimeout(show, 50)
}

function sleep(ms) {
  return new Promise((r) => { subPollTimer = setTimeout(r, ms) })
}

async function waitSubtitleReady(trackId, gen) {
  // Poll status; extract runs in background with nice/ionice — do not touch video.src.
  const part = props.part || 0
  const started = Date.now()
  const maxMs = 10 * 60 * 1000
  while (gen === subSelectGen && Date.now() - started < maxMs) {
    try {
      const { data } = await getSubtitleStatus(props.mediaId, trackId, part)
      if (gen !== subSelectGen) return false
      if (data?.status === 'ready') return true
      if (data?.status === 'error' || data?.status === 'unavailable') {
        throw new Error(data?.error || 'subtitle failed')
      }
    } catch (e) {
      if (gen !== subSelectGen) return false
      // transient network — keep polling a bit
      if (e?.message && /subtitle failed|图字幕|不支持/.test(e.message)) throw e
    }
    await sleep(2000)
  }
  return false
}

async function fetchReadyVtt(trackId) {
  const res = await fetchSubtitleAsync(props.mediaId, trackId, props.part || 0)
  if (res.status === 202) return null
  const body = res.data
  if (typeof body === 'string' && body.includes('WEBVTT')) return body
  // unexpected JSON
  return null
}

async function selectSubtitle(trackId) {
  const gen = ++subSelectGen
  stopSubPoll()
  selectedSubId.value = trackId
  subMenuOpen.value = false
  subPreparingId.value = null
  clearVideoTracks()
  revokeSubBlob()
  if (!trackId || !props.mediaId) return

  const meta = subtitleTracks.value.find((tr) => tr.id === trackId)
  if (meta && meta.supported === false) {
    flashHint(meta.unsupported_reason || t('player.subExtractFail'))
    selectedSubId.value = null
    return
  }

  // External / already-cached: fetch VTT as text → blob URL (never hang <track> on extract).
  const instant = !meta || meta.source === 'external' || meta.cached
  if (!instant) {
    subPreparingId.value = trackId
    flashHint(t('player.subPreparing'))
  }

  try {
    // Kick prepare (202) or get VTT (200) without blocking playback.
    let vtt = await fetchReadyVtt(trackId)
    if (gen !== subSelectGen) return
    if (!vtt) {
      subPreparingId.value = trackId
      const ok = await waitSubtitleReady(trackId, gen)
      if (gen !== subSelectGen) return
      if (!ok) throw new Error('timeout')
      vtt = await fetchReadyVtt(trackId)
      if (gen !== subSelectGen) return
      if (!vtt) throw new Error('empty')
    }
    attachVttBlob(vtt, meta)
    // Mark cached in menu for next open
    if (meta) meta.cached = true
    subPreparingId.value = null
  } catch (e) {
    if (gen !== subSelectGen) return
    subPreparingId.value = null
    selectedSubId.value = null
    clearVideoTracks()
    flashHint(t('player.subExtractFail'))
  }
}

onMounted(() => {
  if (props.mediaDuration > 0) duration.value = props.mediaDuration
  document.addEventListener('keydown', onKeydown)
  document.addEventListener('keyup', onKeyup)
  document.addEventListener('fullscreenchange', () => {
    isFullscreen.value = !!document.fullscreenElement
  })
  document.addEventListener('click', onDocClick)
  showControls()
  loadSubtitles()
})
function onDocClick() {
  subMenuOpen.value = false
}

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
  document.removeEventListener('keyup', onKeyup)
  document.removeEventListener('click', onDocClick)
  clearTimeout(controlsTimer)
  clearTimeout(longPressTimer)
  clearTimeout(hintTimer)
  stopSubPoll()
  subSelectGen += 1
  revokeSubBlob()
  endRewind()
  if (props.mediaId && currentTime.value > 5) {
    saveProgress(props.mediaId, {
      position: currentTime.value,
      duration: duration.value || 0,
      part: props.part || 0
    }).catch(() => {})
  }
})

function switchPart(i) {
  emit('part', i)
}

watch(() => props.mediaDuration, (v) => {
  if (v > 0) duration.value = v
})

watch(() => props.src, () => {
  remuxBaseStart = 0
  if (props.mediaDuration > 0) duration.value = props.mediaDuration
  if (videoEl.value) {
    videoEl.value.load()
    videoEl.value.play().catch(() => {})
  }
  loadSubtitles()
})

watch(() => [props.mediaId, props.part], () => {
  loadSubtitles()
})

watch(() => prefs.defaultSpeed, (v) => {
  if (!speedBoosting.value) {
    baseRate = v
    applyRate(v)
  }
})

function formatTime(s) {
  if (!s || !isFinite(s)) return '0:00'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = Math.floor(s % 60)
  if (h > 0) return `${h}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`
  return `${m}:${String(sec).padStart(2,'0')}`
}
</script>

<style scoped>
.player {
  position: fixed; inset: 0; background: #000; z-index: 9999;
  display: flex; align-items: center; justify-content: center;
  user-select: none; cursor: none;
}
.player.controls-visible { cursor: default; }
.player video {
  width: 100%; height: 100%; object-fit: contain; pointer-events: none;
}

.buffering {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  pointer-events: none;
}
.spinner {
  width: 48px; height: 48px; border: 3px solid rgba(255,255,255,0.2);
  border-top-color: #fff; border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.play-error {
  position: absolute; inset: 0; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 14px;
  background: rgba(0,0,0,0.55); z-index: 6; padding: 24px; text-align: center;
}
.play-error-msg {
  color: #fff; font-size: 15px; line-height: 1.5; max-width: 420px;
  text-shadow: 0 1px 2px rgba(0,0,0,0.8);
}
.play-error-btn {
  background: var(--accent, #ffa31a); color: #111; border: none;
  border-radius: 6px; padding: 8px 18px; font-size: 14px; font-weight: 600;
  cursor: pointer;
}

.center-play {
  position: absolute; display: flex; align-items: center; justify-content: center;
  opacity: 0.7; transition: opacity 0.2s; cursor: pointer; z-index: 2;
}
.player:not(.paused) .center-play { display: none; }

.gesture-hint {
  position: absolute; top: 22%; left: 50%; transform: translateX(-50%);
  background: rgba(0,0,0,.7); color: #fff; padding: 8px 16px; border-radius: 8px;
  font-size: 18px; font-weight: 600; pointer-events: none; z-index: 5;
}
.speed-badge {
  position: absolute; top: 18%; right: 8%;
  background: rgba(255,163,26,.92); color: #fff; padding: 6px 12px; border-radius: 6px;
  font-size: 16px; font-weight: 700; pointer-events: none; z-index: 5;
}

.top-bar {
  position: absolute; top: 0; left: 0; right: 0;
  padding: 16px 20px; display: flex; align-items: center; gap: 12px;
  background: linear-gradient(to bottom, rgba(0,0,0,0.7) 0%, transparent 100%);
  transition: opacity 0.3s;
  opacity: 0; pointer-events: none; z-index: 3;
}
.player.controls-visible .top-bar { opacity: 1; pointer-events: auto; }
.title { font-size: 16px; font-weight: 500; color: #fff; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.top-right { display: flex; align-items: center; gap: 4px; }

.bottom-bar {
  position: absolute; bottom: 0; left: 0; right: 0;
  padding: 0 16px 12px;
  background: linear-gradient(to top, rgba(0,0,0,0.8) 0%, transparent 100%);
  transition: opacity 0.3s;
  opacity: 0; pointer-events: none; z-index: 3;
}
.player.controls-visible .bottom-bar { opacity: 1; pointer-events: auto; }

.progress-container {
  position: relative; width: 100%; height: 20px;
  display: flex; align-items: center; cursor: pointer;
}
.progress-bg {
  width: 100%; height: 4px; background: rgba(255,255,255,0.2);
  border-radius: 2px; position: relative; transition: height 0.1s;
}
.progress-container:hover .progress-bg { height: 6px; }
.progress-buffered {
  position: absolute; top: 0; left: 0; height: 100%;
  background: rgba(255,255,255,0.3); border-radius: 2px;
}
.progress-played {
  position: absolute; top: 0; left: 0; height: 100%;
  background: var(--accent); border-radius: 2px;
}
.progress-thumb {
  position: absolute; right: -6px; top: 50%; transform: translateY(-50%);
  width: 14px; height: 14px; background: var(--accent); border-radius: 50%;
  opacity: 0; transition: opacity 0.1s;
}
.progress-container:hover .progress-thumb { opacity: 1; }
.hover-tooltip {
  position: absolute; bottom: 18px; transform: translateX(-50%);
  background: rgba(0,0,0,0.85); color: #fff; padding: 3px 8px;
  border-radius: 4px; font-size: 12px; white-space: nowrap; pointer-events: none;
}

.controls-row {
  display: flex; align-items: center; justify-content: space-between;
  margin-top: 8px;
}
.controls-left, .controls-right { display: flex; align-items: center; gap: 4px; }

.icon-btn {
  background: none; border: none; padding: 6px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  border-radius: 4px; transition: background 0.15s;
}
.icon-btn:hover { background: rgba(255,255,255,0.15); }
.icon-btn.active { color: var(--accent); }

.volume-group { display: flex; align-items: center; gap: 2px; }
.volume-slider-wrap { width: 0; overflow: hidden; transition: width 0.2s; }
.volume-group:hover .volume-slider-wrap { width: 80px; }
.volume-slider {
  width: 80px; height: 4px; -webkit-appearance: none; appearance: none;
  background: rgba(255,255,255,0.3); border-radius: 2px; outline: none;
}
.volume-slider::-webkit-slider-thumb {
  -webkit-appearance: none; width: 12px; height: 12px;
  background: #fff; border-radius: 50%; cursor: pointer;
}

.time-display {
  color: rgba(255,255,255,0.8); font-size: 13px; margin-left: 8px;
  font-variant-numeric: tabular-nums;
}

.speed-btn {
  color: rgba(255,255,255,0.8); font-size: 13px; font-weight: 600;
  padding: 4px 8px; min-width: 40px;
}

.sub-group { position: relative; }
.sub-menu {
  position: absolute; bottom: 42px; right: 0;
  min-width: 180px; max-height: 260px; overflow: auto;
  background: rgba(20,20,20,0.95); border: 1px solid rgba(255,255,255,0.12);
  border-radius: 8px; padding: 8px 0; z-index: 8;
}
.sub-menu-title {
  color: rgba(255,255,255,0.55); font-size: 11px; padding: 4px 14px 8px;
  text-transform: uppercase; letter-spacing: 0.04em;
}
.sub-item {
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  width: 100%; background: none; border: none; color: #fff;
  padding: 8px 14px; font-size: 13px; cursor: pointer; text-align: left;
}
.sub-item:hover { background: rgba(255,255,255,0.08); }
.sub-item.active { color: var(--accent); }
.sub-meta { color: rgba(255,255,255,0.4); font-size: 11px; flex-shrink: 0; }
.sub-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sub-item.preparing .sub-meta { color: var(--accent, #ffa31a); }
.sub-item:disabled { opacity: 0.45; cursor: not-allowed; }
.sub-empty { color: rgba(255,255,255,0.45); font-size: 12px; padding: 8px 14px; }

/* HTML5 cue styling */
.player video::cue {
  background: rgba(0,0,0,0.55);
  color: #fff;
  font-size: 1.05em;
  text-shadow: 0 1px 2px rgba(0,0,0,0.9);
  line-height: 1.35;
}
</style>
