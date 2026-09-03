<template>
  <div class="card" @click="$emit('click', item)">
    <div class="poster">
      <img
        v-if="posterSrc"
        :src="posterSrc"
        :alt="item.title"
        @load="loaded=true"
        @error="err=true"
        v-show="loaded && !err"
      />
      <div v-if="!loaded && !err" class="skeleton">
        <svg viewBox="0 0 24 24" width="32" height="32"><path d="M18 4l2 4h-3l-2-4h-2l2 4h-3l-2-4H8l2 4H7L5 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V4h-4z" fill="#333"/></svg>
      </div>
      <div v-if="err" class="fallback">
        <span>{{ item.title }}</span>
      </div>

      <div class="overlay">
        <div class="play-btn">
          <svg viewBox="0 0 24 24" width="32" height="32"><path d="M8 5v14l11-7z" fill="#fff"/></svg>
        </div>
      </div>

      <div class="rating" v-if="item.rating">
        <svg viewBox="0 0 24 24" width="12" height="12"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" fill="#f0c040"/></svg>
        {{ item.rating.toFixed(1) }}
      </div>

      <div class="progress" v-if="progress > 0">
        <div class="bar" :style="{width: progress+'%'}"></div>
      </div>
    </div>

    <div class="info">
      <div class="title">{{ item.title }}</div>
      <div class="meta">
        <span v-if="item.year">{{ item.year }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { getPosterUrl } from '@/api/media'

const props = defineProps({ item: { type: Object, required: true } })
defineEmits(['click'])

const loaded = ref(false)
const err = ref(false)

const posterSrc = computed(() => {
  if (!props.item) return ''
  const url = props.item.poster_url
  if (url && typeof url === 'string' && url.startsWith('http')) return url
  if (url || props.item.id) return getPosterUrl(props.item.id)
  return ''
})

const progress = computed(() => {
  const dur = Number(props.item.duration) || 0
  const pos = Number(props.item.progress) || parseFloat(localStorage.getItem('mv_pos_' + props.item.id) || '0')
  if (dur > 0 && pos > 0) return Math.min(100, (pos / dur) * 100)
  return 0
})
</script>

<style scoped>
.card {
  cursor: pointer; border-radius: 6px; overflow: hidden;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.card:hover { transform: scale(1.05); z-index: 10; box-shadow: 0 8px 24px rgba(0,0,0,0.5); }

.poster {
  position: relative; aspect-ratio: 2/3; background: #1a1a1a; border-radius: 6px; overflow: hidden;
}
.poster img { width: 100%; height: 100%; object-fit: cover; }
.skeleton, .fallback {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
}
.skeleton { color: #333; animation: pulse 1.5s infinite; }
@keyframes pulse { 0%,100% { opacity: 0.3; } 50% { opacity: 0.7; } }
.fallback { background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 12px; }
.fallback span { color: #666; font-size: 12px; text-align: center; line-height: 1.4; word-break: break-all; }

.overlay {
  position: absolute; inset: 0; background: linear-gradient(to top, rgba(0,0,0,0.6), transparent 50%);
  display: flex; align-items: center; justify-content: center;
  opacity: 0; transition: opacity 0.2s;
}
.card:hover .overlay { opacity: 1; }
.play-btn {
  width: 44px; height: 44px; border-radius: 50%;
  background: rgba(255,255,255,0.15); backdrop-filter: blur(8px);
  display: flex; align-items: center; justify-content: center;
}

.rating {
  position: absolute; top: 6px; right: 6px;
  background: rgba(0,0,0,0.75); color: #f0c040;
  padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600;
  display: flex; align-items: center; gap: 3px;
}

.progress { position: absolute; bottom: 0; left: 0; right: 0; height: 3px; background: rgba(255,255,255,0.2); }
.bar { height: 100%; background: var(--accent); border-radius: 0 2px 2px 0; }

.info { padding: 8px 2px 4px; }
.title { font-size: 13px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #ddd; }
.meta { font-size: 11px; color: #666; margin-top: 2px; }
</style>
