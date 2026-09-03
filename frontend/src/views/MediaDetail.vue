<template>
  <div class="detail" v-if="item">
    <div v-if="fanartSrc" class="bg" :style="bgStyle"></div>
    <div class="content">
      <div class="row">
        <div class="poster">
          <img v-if="posterSrc" :src="posterSrc" :alt="item.title" />
          <div v-else class="ph"><svg viewBox="0 0 24 24" width="48" height="48"><path d="M18 4l2 4h-3l-2-4h-2l2 4h-3l-2-4H8l2 4H7L5 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V4h-4z" fill="#333"/></svg></div>
        </div>
        <div class="info">
          <h1>{{ item.title }}</h1>
          <p v-if="item.original_title && item.original_title!==item.title" class="sub">{{ item.original_title }}</p>
          <div class="tags">
            <el-tag v-if="item.year" type="info" size="small">{{ item.year }}</el-tag>
            <el-tag :type="item.category==='tvshow'?'warning':'primary'" size="small">{{ item.category==='tvshow'?t('home.show'):t('home.movie') }}</el-tag>
            <span v-if="item.rating" class="rate"><svg viewBox="0 0 24 24" width="14" height="14"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" fill="#f0c040"/></svg> {{ item.rating.toFixed(1) }}</span>
          </div>
          <div class="genre" v-if="item.genre">
            <el-tag v-for="g in item.genre.split(',')" :key="g" size="small" effect="plain" type="info">{{ g.trim() }}</el-tag>
          </div>
          <p v-if="item.director" class="dim"><strong>{{ t('media.director') }}</strong> {{ item.director }}</p>
          <p v-if="cast.length" class="dim"><strong>{{ t('media.cast') }}</strong> {{ cast.join('、') }}</p>
          <div v-if="item.plot" class="plot"><h3>{{ t('media.plot') }}</h3><p>{{ item.plot }}</p></div>
          <div class="btns">
            <el-button type="primary" size="large" round @click="play"><svg viewBox="0 0 24 24" width="18" height="18" style="margin-right:6px"><path d="M8 5v14l11-7z" fill="#fff"/></svg>{{ t('media.play') }}</el-button>
            <el-button v-if="savedPos>0" size="large" round @click="play">{{ t('media.resume', { time: fmtTime(savedPos) }) }}</el-button>
          </div>
          <div v-if="parts.length>1" class="parts">
            <el-button v-for="(p,i) in parts" :key="i" size="small" :type="partIndex===i?'primary':'default'" round @click="playPart(i)">{{ p.label || t('media.part', { n: i+1 }) }}</el-button>
          </div>
        </div>
      </div>
    </div>
    <VideoPlayer v-if="playing" :src="streamUrl" :title="item.title" :media-id="item.id" :part="partIndex" :parts="parts" @close="playing=false" @part="playPart" />
  </div>
  <div v-else class="loading"><el-icon :size="32" class="is-loading"><Loading /></el-icon></div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useMediaStore } from '@/stores/media'
import { getStreamUrl, getPosterUrl, getFanartUrl } from '@/api/media'
import { Loading } from '@element-plus/icons-vue'
import VideoPlayer from '@/components/VideoPlayer.vue'
const { t } = useI18n()
const route = useRoute(); const store = useMediaStore()
const item = ref(null); const playing = ref(false); const partIndex = ref(0)
const parts = computed(() => item.value?.extra_files || [])
const streamUrl = computed(() => item.value ? getStreamUrl(item.value.id, partIndex.value) : '')
const posterSrc = computed(() => {
  if (!item.value) return ''
  if (item.value.poster_url?.startsWith('http')) return item.value.poster_url
  return item.value.poster_url || item.value.id ? getPosterUrl(item.value.id) : ''
})
const fanartSrc = computed(() => {
  if (!item.value) return ''
  if (item.value.fanart_url?.startsWith('http')) return item.value.fanart_url
  return item.value.fanart_url || item.value.id ? getFanartUrl(item.value.id) : ''
})
const cast = computed(() => { try { return JSON.parse(item.value?.cast_list||'[]') } catch { return [] } })
const savedPos = computed(() => item.value ? Number(item.value.progress || localStorage.getItem('mv_pos_' + item.value.id) || 0) : 0)
const bgStyle = computed(() => fanartSrc.value ? { backgroundImage: 'url(' + fanartSrc.value + ')' } : {})
onMounted(async () => {
  item.value = await store.fetchDetail(route.params.id)
  if (item.value?.progress_part) partIndex.value = item.value.progress_part
})
function play() { playing.value = true }
function playPart(i) { partIndex.value = i; playing.value = true }
function fmtTime(s) { const m=Math.floor(s/60), sec=Math.floor(s%60); return m + ':' + String(sec).padStart(2,'0') }
</script>
<style scoped>
.detail { position:relative; min-height:calc(100vh - 100px); }
.bg { position:fixed; top:0; left:0; right:0; height:500px; background-size:cover; background-position:center top; opacity:0.1; pointer-events:none; mask-image:linear-gradient(to bottom,black 50%,transparent); }
.content { position:relative; z-index:1; }
.row { display:flex; gap:32px; }
.poster { flex-shrink:0; width:220px; }
.poster img { width:100%; border-radius:8px; box-shadow:0 8px 30px rgba(0,0,0,0.6); }
.ph { width:220px; height:330px; background:var(--bg-card); border-radius:8px; display:flex; align-items:center; justify-content:center; }
.info { flex:1; display:flex; flex-direction:column; gap:10px; }
.info h1 { font-size:26px; font-weight:700; }
.sub { color:var(--text-dim); font-size:14px; }
.tags { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.rate { display:flex; align-items:center; gap:4px; color:#f0c040; font-size:16px; font-weight:700; }
.genre { display:flex; gap:6px; flex-wrap:wrap; }
.dim { color:var(--text-dim); font-size:13px; } .dim strong { color:var(--text); margin-right:4px; }
.plot h3 { font-size:14px; color:#aaa; margin-bottom:6px; }
.plot p { color:var(--text-dim); font-size:13px; line-height:1.8; }
.btns { display:flex; gap:10px; margin-top:8px; }
.parts { display:flex; gap:8px; flex-wrap:wrap; margin-top:8px; }
.loading { display:flex; justify-content:center; padding:80px; color:var(--accent); }
</style>
