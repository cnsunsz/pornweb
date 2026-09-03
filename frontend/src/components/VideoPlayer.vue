<template>
  <div
    ref="playerEl"
    class="player"
    :class="{ fullscreen: isFullscreen, 'controls-visible': controlsVisible, paused: isPaused }"
    @mousemove="showControls"
    @mouseleave="hideControlsDelayed"
    @click="togglePlay"
    @dblclick="toggleFullscreen"
  >
    <!-- Video -->
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

    <!-- Buffering spinner -->
    <div v-if="isBuffering" class="buffering">
      <div class="spinner"></div>
    </div>

    <!-- Center play button (when paused) -->
    <div v-if="isPaused && !isBuffering" class="center-play">
      <svg viewBox="0 0 24 24" width="72" height="72"><path d="M8 5v14l11-7z" fill="white"/></svg>
    </div>

    <!-- Top bar: title + back -->
    <div class="top-bar" @click.stop>
      <button class="icon-btn" @click="$emit('close')" :title="t('player.back')">
        <svg viewBox="0 0 24 24" width="24" height="24"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z" fill="white"/></svg>
      </button>
      <span class="title">{{ title }}</span>
    </div>

    <!-- Bottom controls -->
    <div class="bottom-bar" @click.stop>
      <!-- Progress bar -->
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
        <!-- Hover time tooltip -->
        <div v-if="hoverTime !== null" class="hover-tooltip" :style="{ left: hoverX + 'px' }">
          {{ formatTime(hoverTime) }}
        </div>
      </div>

      <!-- Control buttons -->
      <div class="controls-row">
        <div class="controls-left">
          <!-- Play/Pause -->
          <button class="icon-btn" @click.stop="togglePlay" :title="isPaused ? t('player.play') : t('player.pause')">
            <svg v-if="isPaused" viewBox="0 0 24 24" width="28" height="28"><path d="M8 5v14l11-7z" fill="white"/></svg>
            <svg v-else viewBox="0 0 24 24" width="28" height="28"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" fill="white"/></svg>
          </button>

          <!-- Skip backward -->
          <button class="icon-btn" @click.stop="skip(-10)" :title="t('player.back10')">
            <svg viewBox="0 0 24 24" width="22" height="22"><path d="M11.99 5V1l-5 5 5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6h-2c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z" fill="white"/><text x="9" y="16" font-size="7" fill="white" font-weight="bold">10</text></svg>
          </button>

          <!-- Skip forward -->
          <button class="icon-btn" @click.stop="skip(10)" :title="t('player.fwd10')">
            <svg viewBox="0 0 24 24" width="22" height="22"><path d="M12.01 5V1l5 5-5 5V7c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6h2c0 4.42-3.58 8-8 8s-8-3.58-8-8 3.58-8 8-8z" fill="white"/><text x="9" y="16" font-size="7" fill="white" font-weight="bold">10</text></svg>
          </button>

          <!-- Volume -->
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

          <!-- Time -->
          <span class="time-display">
            {{ formatTime(currentTime) }} / {{ formatTime(duration) }}
          </span>
        </div>

        <div class="controls-right">
          <!-- Parts -->
          <div v-if="parts && parts.length > 1" class="parts-group" @click.stop>
            <button
              v-for="(p, i) in parts"
              :key="i"
              class="icon-btn speed-btn"
              :class="{ active: part === i }"
              @click="switchPart(i)"
            >{{ p.label || (i+1) }}</button>
          </div>

          <!-- Playback speed -->
          <div class="speed-group" @click.stop>
            <button class="icon-btn speed-btn" @click="cycleSpeed">
              {{ playbackRate }}x
            </button>
          </div>

          <!-- Picture in Picture -->
          <button class="icon-btn" @click.stop="togglePiP" :title="t('player.pip')">
            <svg viewBox="0 0 24 24" width="22" height="22"><path d="M19 11h-8v6h8v-6zm4 8V4.98C23 3.88 22.1 3 21 3H3c-1.1 0-2 .88-2 1.98V19c0 1.1.9 2 2 2h18c1.1 0 2-.9 2-2zm-2 .02H3V4.97h18v14.05z" fill="white"/></svg>
          </button>

          <!-- Fullscreen -->
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
import { saveProgress } from '@/api/media'

const { t } = useI18n()
const props = defineProps({
  src: { type: String, required: true },
  title: { type: String, default: '' },
  mediaId: { type: Number, default: null },
  part: { type: Number, default: 0 },
  parts: { type: Array, default: () => [] },
})

const emit = defineEmits(['close', 'part'])

const playerEl = ref(null)
const videoEl = ref(null)
const progressEl = ref(null)

const isPaused = ref(true)
const isBuffering = ref(false)
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

let controlsTimer = null
let seeking = false
let lastSave = 0

// Controls visibility
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

// Play/Pause
function togglePlay() {
  if (!videoEl.value) return
  if (videoEl.value.paused) videoEl.value.play()
  else videoEl.value.pause()
}

// Seek
function skip(sec) {
  if (!videoEl.value) return
  videoEl.value.currentTime = Math.max(0, Math.min(duration.value, videoEl.value.currentTime + sec))
  showControls()
}

// Volume
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

// Speed
function cycleSpeed() {
  const speeds = [0.5, 0.75, 1, 1.25, 1.5, 2]
  const idx = speeds.indexOf(playbackRate.value)
  playbackRate.value = speeds[(idx + 1) % speeds.length]
  if (videoEl.value) videoEl.value.playbackRate = playbackRate.value
}

// Fullscreen
function toggleFullscreen() {
  if (!playerEl.value) return
  if (!document.fullscreenElement) {
    playerEl.value.requestFullscreen()
    isFullscreen.value = true
  } else {
    document.exitFullscreen()
    isFullscreen.value = false
  }
}

// PiP
function togglePiP() {
  if (!videoEl.value) return
  if (document.pictureInPictureElement) document.exitPictureInPicture()
  else videoEl.value.requestPictureInPicture()
}

// Progress seeking
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
function seekTo(e) {
  if (!progressEl.value || !videoEl.value) return
  const rect = progressEl.value.getBoundingClientRect()
  const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  videoEl.value.currentTime = pct * duration.value
}
function onProgressHover(e) {
  if (!progressEl.value) return
  const rect = progressEl.value.getBoundingClientRect()
  const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  hoverTime.value = pct * duration.value
  hoverX.value = e.clientX - rect.left
}

// Video events
function onLoaded() {
  duration.value = videoEl.value.duration
  // Restore position
  const saved = getSavedPosition()
  if (saved > 0) videoEl.value.currentTime = saved
  // Restore volume
  const savedVol = localStorage.getItem('mv_volume')
  if (savedVol !== null) setVolume(parseFloat(savedVol))
}
function onTimeUpdate() {
  if (!videoEl.value || seeking) return
  currentTime.value = videoEl.value.currentTime
  duration.value = videoEl.value.duration || 0
  playedPercent.value = duration.value ? (currentTime.value / duration.value) * 100 : 0
  // Buffered
  if (videoEl.value.buffered.length > 0) {
    bufferedPercent.value = (videoEl.value.buffered.end(videoEl.value.buffered.length - 1) / duration.value) * 100
  }
  // Save position periodically
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
}

// Position save/restore
function getStorageKey() { return props.mediaId ? `mv_pos_${props.mediaId}` : '' }
function savePosition() {
  const key = getStorageKey()
  if (key && currentTime.value > 5) {
    localStorage.setItem(key, String(Math.floor(currentTime.value)))
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

// Keyboard shortcuts
function onKeydown(e) {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
  switch (e.key) {
    case ' ': e.preventDefault(); togglePlay(); break
    case 'ArrowLeft': e.preventDefault(); skip(-10); break
    case 'ArrowRight': e.preventDefault(); skip(10); break
    case 'ArrowUp': e.preventDefault(); setVolume(Math.min(1, volume.value + 0.1)); break
    case 'ArrowDown': e.preventDefault(); setVolume(Math.max(0, volume.value - 0.1)); break
    case 'f': case 'F': e.preventDefault(); toggleFullscreen(); break
    case 'm': case 'M': e.preventDefault(); toggleMute(); break
    case 'Escape': if (isFullscreen.value) toggleFullscreen(); else emit('close'); break
  }
}

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
  document.addEventListener('fullscreenchange', () => {
    isFullscreen.value = !!document.fullscreenElement
  })
  showControls()
})
onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
  clearTimeout(controlsTimer)
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

watch(() => props.src, () => {
  if (videoEl.value) {
    videoEl.value.load()
    videoEl.value.play().catch(() => {})
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
  width: 100%; height: 100%; object-fit: contain;
}

/* Buffering */
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

/* Center play */
.center-play {
  position: absolute; display: flex; align-items: center; justify-content: center;
  pointer-events: none; opacity: 0.7; transition: opacity 0.2s;
}
.player:not(.paused) .center-play { display: none; }

/* Top bar */
.top-bar {
  position: absolute; top: 0; left: 0; right: 0;
  padding: 16px 20px; display: flex; align-items: center; gap: 12px;
  background: linear-gradient(to bottom, rgba(0,0,0,0.7) 0%, transparent 100%);
  transition: opacity 0.3s;
  opacity: 0; pointer-events: none;
}
.player.controls-visible .top-bar { opacity: 1; pointer-events: auto; }
.title { font-size: 16px; font-weight: 500; color: #fff; }

/* Bottom bar */
.bottom-bar {
  position: absolute; bottom: 0; left: 0; right: 0;
  padding: 0 16px 12px;
  background: linear-gradient(to top, rgba(0,0,0,0.8) 0%, transparent 100%);
  transition: opacity 0.3s;
  opacity: 0; pointer-events: none;
}
.player.controls-visible .bottom-bar { opacity: 1; pointer-events: auto; }

/* Progress */
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
  background: #e50914; border-radius: 2px;
}
.progress-thumb {
  position: absolute; right: -6px; top: 50%; transform: translateY(-50%);
  width: 14px; height: 14px; background: #e50914; border-radius: 50%;
  opacity: 0; transition: opacity 0.1s;
}
.progress-container:hover .progress-thumb { opacity: 1; }
.hover-tooltip {
  position: absolute; bottom: 18px; transform: translateX(-50%);
  background: rgba(0,0,0,0.85); color: #fff; padding: 3px 8px;
  border-radius: 4px; font-size: 12px; white-space: nowrap; pointer-events: none;
}

/* Controls row */
.controls-row {
  display: flex; align-items: center; justify-content: space-between;
  margin-top: 8px;
}
.controls-left, .controls-right { display: flex; align-items: center; gap: 4px; }

/* Icon button */
.icon-btn {
  background: none; border: none; padding: 6px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  border-radius: 4px; transition: background 0.15s;
}
.icon-btn:hover { background: rgba(255,255,255,0.15); }

/* Volume */
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

/* Time */
.time-display {
  color: rgba(255,255,255,0.8); font-size: 13px; margin-left: 8px;
  font-variant-numeric: tabular-nums;
}

/* Speed */
.speed-btn {
  color: rgba(255,255,255,0.8); font-size: 13px; font-weight: 600;
  padding: 4px 8px; min-width: 40px;
}
</style>
