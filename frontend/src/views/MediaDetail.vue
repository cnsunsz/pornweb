<template>
  <div class="detail" v-if="item">
    <div v-if="fanartSrc" class="bg" :style="bgStyle"></div>
    <div class="content">
      <!-- Hero: poster + meta + play CTA -->
      <div class="hero">
        <div class="poster">
          <img v-if="posterSrc" :src="posterSrc" :alt="item.title" />
          <div v-else class="ph">
            <svg viewBox="0 0 24 24" width="48" height="48"><path d="M18 4l2 4h-3l-2-4h-2l2 4h-3l-2-4H8l2 4H7L5 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V4h-4z" fill="#333"/></svg>
          </div>
          <div class="poster-play" @click="play">
            <svg viewBox="0 0 24 24" width="36" height="36"><path d="M8 5v14l11-7z" fill="#111"/></svg>
          </div>
        </div>
        <div class="info">
          <h1>{{ item.title }}</h1>
          <p v-if="item.original_title && item.original_title!==item.title" class="sub">{{ item.original_title }}</p>
          <div class="tags">
            <span v-if="item.year" class="pill">{{ item.year }}</span>
            <span class="pill accent">{{ item.category==='tvshow'?t('home.show'):t('home.movie') }}</span>
            <span v-if="durationLabel" class="pill">{{ durationLabel }}</span>
            <span v-if="item.rating" class="rate">
              <svg viewBox="0 0 24 24" width="14" height="14"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" fill="var(--accent)"/></svg>
              {{ item.rating.toFixed(1) }}
            </span>
          </div>
          <div class="genre" v-if="item.genre">
            <span v-for="g in item.genre.split(',')" :key="g" class="genre-chip">{{ g.trim() }}</span>
          </div>
          <p v-if="item.director" class="dim"><strong>{{ t('media.director') }}</strong> {{ item.director }}</p>
          <div v-if="cast.length" class="dim cast-row">
            <strong>{{ t('media.cast') }}</strong>
            <router-link
              v-for="name in cast"
              :key="name"
              class="cast-chip"
              :to="{ name: 'ActorDetail', params: { name } }"
            >{{ name }}</router-link>
          </div>
          <div v-if="item.plot" class="plot">
            <h3>{{ t('media.plot') }}</h3>
            <p>{{ item.plot }}</p>
          </div>
          <div class="btns">
            <el-button type="primary" size="large" @click="play">
              <svg viewBox="0 0 24 24" width="18" height="18" style="margin-right:6px"><path d="M8 5v14l11-7z" fill="#111"/></svg>
              {{ t('media.play') }}
            </el-button>
            <el-button v-if="savedPos>0" size="large" @click="play">{{ t('media.resume', { time: fmtTime(savedPos) }) }}</el-button>
            <el-button v-if="auth.isAdmin" size="large" :loading="scraping" @click="doScrape">{{ t('media.scrape') }}</el-button>
          </div>
          <div v-if="parts.length>1" class="parts">
            <button
              v-for="(p,i) in parts"
              :key="i"
              class="part-btn"
              :class="{ on: partIndex===i }"
              @click="playPart(i)"
            >{{ p.label || t('media.part', { n: i+1 }) }}</button>
          </div>
        </div>
      </div>

      <!-- Related cover wall -->
      <section v-if="related.length" class="related">
        <h2 class="section-title">{{ t('media.related') }}</h2>
        <div class="tube-grid">
          <MediaCard v-for="r in related" :key="r.id" :item="r" @click="go(r)" />
        </div>
      </section>
    </div>
    <VideoPlayer
      v-if="playing"
      :src="streamUrl"
      :title="item.title"
      :media-id="item.id"
      :part="partIndex"
      :parts="parts"
      @close="playing=false"
      @part="playPart"
    />
  </div>
  <div v-else class="loading"><el-icon :size="32" class="is-loading"><Loading /></el-icon></div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useMediaStore } from '@/stores/media'
import { getStreamUrl, getPosterUrl, getFanartUrl, getMediaList, scrapeMedia } from '@/api/media'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import { apiError } from '@/i18n'
import { Loading } from '@element-plus/icons-vue'
import VideoPlayer from '@/components/VideoPlayer.vue'
import MediaCard from '@/components/MediaCard.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useMediaStore()
const auth = useAuthStore()
const item = ref(null)
const playing = ref(false)
const partIndex = ref(0)
const related = ref([])
const scraping = ref(false)

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
const cast = computed(() => {
  try { return JSON.parse(item.value?.cast_list || '[]') } catch { return [] }
})
const savedPos = computed(() => item.value ? Number(item.value.progress || localStorage.getItem('mv_pos_' + item.value.id) || 0) : 0)
const bgStyle = computed(() => fanartSrc.value ? { backgroundImage: 'url(' + fanartSrc.value + ')' } : {})
const durationLabel = computed(() => {
  const s = Number(item.value?.duration) || 0
  if (s <= 0) return ''
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = Math.floor(s % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
  return `${m}:${String(sec).padStart(2, '0')}`
})

async function load() {
  playing.value = false
  item.value = await store.fetchDetail(route.params.id)
  if (item.value?.progress_part) partIndex.value = item.value.progress_part
  await loadRelated()
}

async function loadRelated() {
  related.value = []
  if (!item.value) return
  try {
    const firstGenre = (item.value.genre || '').split(',')[0]?.trim()
    const params = { page: 1, page_size: 18, sort: 'newest' }
    if (firstGenre) params.genre = firstGenre
    else if (item.value.folder) params.folder = item.value.folder
    const res = await getMediaList(params)
    related.value = (res.data.items || []).filter((x) => x.id !== item.value.id).slice(0, 12)
  } catch (e) {
    console.error('related', e)
  }
}

onMounted(load)
watch(() => route.params.id, load)


async function doScrape() {
  if (!item.value) return
  scraping.value = true
  try {
    const res = await scrapeMedia(item.value.id, { force: false })
    const data = res.data || {}
    if (data.item) item.value = data.item
    if ((data.changed || []).length) ElMessage.success(t('media.scrapeOk'))
    else ElMessage.info(t('media.scrapeNone'))
  } catch (e) {
    ElMessage.error(apiError(e, t) || t('media.scrapeFail'))
  } finally {
    scraping.value = false
  }
}

function play() { playing.value = true }
function playPart(i) { partIndex.value = i; playing.value = true }
function go(r) { router.push('/media/' + r.id) }
function fmtTime(s) {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return m + ':' + String(sec).padStart(2, '0')
}
</script>

<style scoped>
.detail { position: relative; min-height: calc(100vh - 80px); }
.bg {
  position: fixed; top: 0; left: 0; right: 0; height: 420px;
  background-size: cover; background-position: center top; opacity: 0.18;
  pointer-events: none;
  mask-image: linear-gradient(to bottom, black 40%, transparent);
}
.content { position: relative; z-index: 1; }
.hero {
  display: flex; gap: 28px; padding: 8px 0 28px;
  border-bottom: 1px solid var(--border);
}
.poster {
  flex-shrink: 0; width: 240px; position: relative;
  border-radius: 6px; overflow: hidden;
  border: 1px solid #2a2a2a;
}
.poster img { width: 100%; display: block; }
.ph {
  width: 240px; height: 360px; background: var(--bg-card);
  display: flex; align-items: center; justify-content: center;
}
.poster-play {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,0.35); opacity: 0; cursor: pointer; transition: opacity 0.15s;
}
.poster:hover .poster-play { opacity: 1; }
.poster-play svg {
  background: var(--accent); border-radius: 50%; padding: 14px;
  width: 64px; height: 64px; box-sizing: content-box;
}
.info { flex: 1; display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.info h1 { font-size: 28px; font-weight: 800; line-height: 1.25; }
.sub { color: var(--text-dim); font-size: 14px; }
.tags { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.pill {
  display: inline-block; padding: 2px 8px; border-radius: 3px;
  background: #222; color: #ddd; font-size: 12px; font-weight: 600;
}
.pill.accent { background: var(--accent); color: #111; }
.rate {
  display: flex; align-items: center; gap: 4px;
  color: var(--accent); font-size: 15px; font-weight: 800;
}
.genre { display: flex; gap: 6px; flex-wrap: wrap; }
.genre-chip {
  padding: 2px 8px; border-radius: 999px; border: 1px solid #333;
  color: var(--text-dim); font-size: 12px;
}
.dim { color: var(--text-dim); font-size: 13px; }
.dim strong { color: var(--text); margin-right: 6px; }
.plot h3 { font-size: 13px; color: #aaa; margin-bottom: 6px; font-weight: 700; }
.plot p { color: var(--text-dim); font-size: 13px; line-height: 1.75; }
.btns { display: flex; gap: 10px; margin-top: 6px; flex-wrap: wrap; }
.parts { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 4px; }
.part-btn {
  border: 1px solid #333; background: #181818; color: #ddd;
  padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: 600;
}
.part-btn.on, .part-btn:hover { border-color: var(--accent); color: var(--accent); }
.cast-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.cast-chip {
  display: inline-block; padding: 3px 10px; border-radius: 999px;
  background: #1c1c1c; color: var(--text); font-size: 12px;
  border: 1px solid #333; transition: background 0.12s, color 0.12s, border-color 0.12s;
}
.cast-chip:hover {
  background: var(--accent); color: #111; border-color: var(--accent);
}
.related { margin-top: 28px; }
.section-title { font-size: 18px; font-weight: 800; margin-bottom: 12px; }
.loading { display: flex; justify-content: center; padding: 80px; color: var(--accent); }
@media (max-width: 720px) {
  .hero { flex-direction: column; align-items: center; }
  .poster, .ph { width: 200px; }
  .ph { height: 300px; }
  .info h1 { font-size: 22px; text-align: center; }
  .info { align-items: center; text-align: center; }
  .cast-row, .tags, .genre, .btns, .parts { justify-content: center; }
}
</style>
