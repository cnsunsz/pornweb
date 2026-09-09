<template>
  <div class="card" @click="$emit('click', item)">
    <div class="poster">
      <img
        v-if="posterSrc"
        :src="posterSrc"
        :alt="item.title"
        loading="lazy"
        @load="loaded=true"
        @error="err=true"
        v-show="loaded && !err"
      />
      <div v-if="!loaded && !err" class="skeleton">
        <svg viewBox="0 0 24 24" width="28" height="28"><path d="M18 4l2 4h-3l-2-4h-2l2 4h-3l-2-4H8l2 4H7L5 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V4h-4z" fill="#333"/></svg>
      </div>
      <div v-if="err" class="fallback">
        <span>{{ item.title }}</span>
      </div>

      <!-- Hover play overlay -->
      <div class="overlay">
        <div class="play-btn">
          <svg viewBox="0 0 24 24" width="28" height="28"><path d="M8 5v14l11-7z" fill="#111"/></svg>
        </div>
      </div>

      <div class="duration" v-if="durationLabel">{{ durationLabel }}</div>

      <div class="rating" v-if="item.rating">
        <svg viewBox="0 0 24 24" width="11" height="11"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" fill="var(--accent)"/></svg>
        {{ Number(item.rating).toFixed(1) }}
      </div>

      <div class="progress" v-if="progress > 0">
        <div class="bar" :style="{width: progress+'%'}"></div>
      </div>
    </div>

    <div class="info">
      <div class="title" :title="item.title">{{ item.title }}</div>
      <div class="meta">
        <span v-if="item.year">{{ item.year }}</span>
        <span v-if="item.year && categoryLabel" class="dot">·</span>
        <span v-if="categoryLabel">{{ categoryLabel }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { getPosterUrl } from '@/api/media'

const props = defineProps({ item: { type: Object, required: true } })
defineEmits(['click'])
const { t } = useI18n()

const loaded = ref(false)
const err = ref(false)

const posterSrc = computed(() => {
  if (!props.item) return ''
  // Always go through /api/media/poster/{id}?token=… — never hotlink Douban/TMDB in <img>
  if (props.item.poster_url || props.item.id) return getPosterUrl(props.item.id)
  return ''
})

const progress = computed(() => {
  const dur = Number(props.item.duration) || 0
  const pos = Number(props.item.progress) || parseFloat(localStorage.getItem('mv_pos_' + props.item.id) || '0')
  if (dur > 0 && pos > 0) return Math.min(100, (pos / dur) * 100)
  return 0
})

const durationLabel = computed(() => {
  const s = Number(props.item.duration) || 0
  if (s <= 0) return ''
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = Math.floor(s % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
  return `${m}:${String(sec).padStart(2, '0')}`
})

const categoryLabel = computed(() => {
  if (props.item.category === 'tvshow') return t('home.show')
  if (props.item.category === 'movie') return t('home.movie')
  return ''
})
</script>

<style scoped>
/* Emby-style poster card: tight radius, compact title under cover */
.card {
  cursor: pointer;
  border-radius: var(--radius);
  overflow: hidden;
  transition: transform 0.12s ease;
}
.card:hover { transform: translateY(-1px); }

.poster {
  position: relative;
  aspect-ratio: 2/3;
  background: #141414;
  border-radius: var(--radius);
  overflow: hidden;
  border: 1px solid rgba(255,255,255,0.04);
  box-shadow: 0 1px 4px rgba(0,0,0,0.35);
}
.card:hover .poster { border-color: var(--accent); }
.poster img { width: 100%; height: 100%; object-fit: cover; display: block; }
.skeleton, .fallback {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
}
.skeleton { color: #333; animation: pulse 1.5s infinite; }
@keyframes pulse { 0%,100% { opacity: 0.3; } 50% { opacity: 0.7; } }
.fallback { background: linear-gradient(135deg, #1a1a1a, #222); padding: 8px; }
.fallback span {
  color: #777; font-size: 10px; text-align: center; line-height: 1.3; word-break: break-all;
}

.overlay {
  position: absolute; inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex; align-items: center; justify-content: center;
  opacity: 0; transition: opacity 0.12s;
}
.card:hover .overlay { opacity: 1; }
.play-btn {
  width: 38px; height: 38px; border-radius: 50%;
  background: var(--accent);
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 3px 12px rgba(0,0,0,0.45);
}

.duration {
  position: absolute; right: 4px; bottom: 5px;
  background: rgba(0,0,0,0.82); color: #fff;
  padding: 1px 4px; border-radius: 2px;
  font-size: 10px; font-weight: 700; font-variant-numeric: tabular-nums;
  letter-spacing: 0.02em;
}

.rating {
  position: absolute; top: 4px; left: 4px;
  background: rgba(0,0,0,0.78); color: var(--accent);
  padding: 1px 4px; border-radius: 2px; font-size: 10px; font-weight: 700;
  display: flex; align-items: center; gap: 2px;
}

.progress {
  position: absolute; bottom: 0; left: 0; right: 0; height: 2.5px;
  background: rgba(255,255,255,0.16);
}
.bar { height: 100%; background: var(--accent); }

.info { padding: 5px 1px 0; }
.title {
  font-size: 12px; font-weight: 600; line-height: 1.28;
  letter-spacing: 0.01em;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; color: #e6e6e6;
}
.card:hover .title { color: var(--accent); }
.meta {
  font-size: 10.5px; color: var(--text-muted); margin-top: 2px;
  display: flex; align-items: center; gap: 3px;
  line-height: 1.2;
}
.dot { opacity: 0.55; }
</style>
